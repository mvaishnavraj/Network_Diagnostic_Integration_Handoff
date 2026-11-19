from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import (
    packet,
    ethernet,
    ether_types
)
from os_ken.topology import event

import networkx as nx
import socket
from os_ken.lib import hub


class TestController(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Network-wide topology graph
        self.network = nx.DiGraph()

        # Connected switches
        self.datapaths = {}

        # Host MAC -> (switch DPID, switch port)
        self.hosts = {}

        # Switch port descriptions
        self.switch_ports = {}

        # Selected path: upper (S1-S2-S3-S4) or lower (S1-S4)
        self.selected_path = "lower"

        # Start local UDP listener for path-selection commands
        hub.spawn(self.path_control_listener)

        self.logger.info(
            "Topology-aware Network Diagnostic Controller started"
        )

    # -------------------------------------------------
    # MANUAL PATH SELECTION
    # -------------------------------------------------

    def path_control_listener(self):
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        control_socket.bind(("127.0.0.1", 9999))

        self.logger.info("Path control listener active on 127.0.0.1:9999")

        while True:
            try:
                data, address = control_socket.recvfrom(1024)
                command = data.decode().strip().lower()

                if command in ("upper", "lower"):
                    self.change_path(command)
                    control_socket.sendto(
                        f"Active path: {self.selected_path}".encode(),
                        address
                    )
                else:
                    control_socket.sendto(
                        b"Invalid command. Use upper or lower.",
                        address
                    )

            except Exception:
                self.logger.exception("Path control listener error")

    def change_path(self, new_path):
        if new_path not in ("upper", "lower"):
            return

        if new_path == self.selected_path:
            self.logger.info("Path already selected: %s", new_path)
            return

        self.selected_path = new_path

        # Delete only priority-10 destination forwarding rules.
        # Preserve table-miss and LLDP discovery rules.
        destination_macs = list(self.hosts.keys())

        for datapath in self.datapaths.values():
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto

            for dst_mac in destination_macs:
                delete = parser.OFPFlowMod(
                    datapath=datapath,
                    command=ofproto.OFPFC_DELETE_STRICT,
                    table_id=ofproto.OFPTT_ALL,
                    priority=10,
                    out_port=ofproto.OFPP_ANY,
                    out_group=ofproto.OFPG_ANY,
                    match=parser.OFPMatch(eth_dst=dst_mac)
                )

                datapath.send_msg(delete)

        self.logger.warning(
            "PATH CHANGED | Active path: %s | Old forwarding rules cleared",
            self.selected_path
        )

    # -------------------------------------------------
    # SWITCH CONNECTION
    # -------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id

        self.datapaths[dpid] = datapath
        self.network.add_node(dpid)

        self.logger.info("Switch connected: %s", dpid)

        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        # Default rule: send unknown packets to controller
        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofproto.OFPP_CONTROLLER,
                ofproto.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(
            datapath,
            priority=0,
            match=match,
            actions=actions
        )

        # Request physical port descriptions
        datapath.send_msg(
            parser.OFPPortDescStatsRequest(datapath)
        )

    # -------------------------------------------------
    # PORT DISCOVERY
    # -------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_description_handler(self, ev):

        datapath = ev.msg.datapath
        dpid = datapath.id

        self.switch_ports[dpid] = {
            port.port_no: port.name
            for port in ev.msg.body
            if port.port_no < datapath.ofproto.OFPP_MAX
        }

        self.logger.info(
            "Port descriptions received | Switch: %s | Ports: %s",
            dpid,
            self.switch_ports[dpid]
        )

    # -------------------------------------------------
    # LLDP TOPOLOGY DISCOVERY
    # -------------------------------------------------

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, ev):

        switch = ev.switch
        dpid = switch.dp.id

        self.network.add_node(dpid)

        self.logger.info(
            "Topology discovery: switch %s detected",
            dpid
        )

    @set_ev_cls(event.EventLinkAdd)
    def link_add_handler(self, ev):

        src = ev.link.src
        dst = ev.link.dst

        self.network.add_edge(
            src.dpid,
            dst.dpid,
            port=src.port_no,
            dst_port=dst.port_no
        )

        self.logger.info(
            "LINK ADDED | %s:%s -> %s:%s",
            src.dpid,
            src.port_no,
            dst.dpid,
            dst.port_no
        )

    @set_ev_cls(event.EventLinkDelete)
    def link_delete_handler(self, ev):
        src = ev.link.src
        dst = ev.link.dst

        if self.network.has_edge(src.dpid, dst.dpid):
            self.network.remove_edge(src.dpid, dst.dpid)

        self.logger.warning(
            "LINK REMOVED | %s -> %s",
            src.dpid,
            dst.dpid
        )

        self.schedule_reroute()

    def schedule_reroute(self):
        # Avoid launching multiple recovery operations for the same failure.
        if getattr(self, "_reroute_pending", False):
            return

        self._reroute_pending = True
        hub.spawn(self._reroute_after_topology_change)

    def clear_destination_flows(self):
        """Delete only our priority-10 destination forwarding rules."""
        destination_macs = list(self.hosts.keys())

        for datapath in self.datapaths.values():
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto

            for dst_mac in destination_macs:
                delete = parser.OFPFlowMod(
                    datapath=datapath,
                    command=ofproto.OFPFC_DELETE_STRICT,
                    table_id=ofproto.OFPTT_ALL,
                    priority=10,
                    out_port=ofproto.OFPP_ANY,
                    out_group=ofproto.OFPG_ANY,
                    match=parser.OFPMatch(eth_dst=dst_mac)
                )

                datapath.send_msg(delete)

    def _reroute_after_topology_change(self):
        try:
            # Wait for both directions of an LLDP-discovered link
            # to be removed from the topology graph.
            hub.sleep(0.5)

            self.logger.warning(
                "TOPOLOGY CHANGED | Recalculating host routes"
            )

            self.clear_destination_flows()

            learned_hosts = list(self.hosts.items())
            installed_routes = 0

            for src_mac, (src_dpid, src_port) in learned_hosts:
                for dst_mac, (dst_dpid, dst_port) in learned_hosts:

                    if src_mac == dst_mac:
                        continue

                    path = self.calculate_path(src_dpid, dst_dpid)

                    if not path:
                        self.logger.error(
                            "REROUTING FAILED | No path from %s to %s",
                            src_dpid,
                            dst_dpid
                        )
                        continue

                    if self.install_path(path, dst_mac, dst_port):
                        installed_routes += 1

                        self.logger.warning(
                            "REROUTED | %s -> %s | Path: %s",
                            src_dpid,
                            dst_dpid,
                            path
                        )

            self.logger.warning(
                "REROUTING COMPLETE | Routes installed: %s",
                installed_routes
            )

        except Exception:
            self.logger.exception("Automatic rerouting failed")

        finally:
            self._reroute_pending = False

    @set_ev_cls(event.EventSwitchLeave)
    def switch_leave_handler(self, ev):
        dpid = ev.switch.dp.id

        if self.network.has_node(dpid):
            self.network.remove_node(dpid)

        self.datapaths.pop(dpid, None)
        self.switch_ports.pop(dpid, None)

        self.logger.warning(
            "Switch disconnected: %s",
            dpid
        )

        self.schedule_reroute()

    # OPENFLOW FLOW INSTALLATION
    # -------------------------------------------------

    def add_flow(
        self,
        datapath,
        priority,
        match,
        actions,
        idle_timeout=0
    ):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        instructions = [
            parser.OFPInstructionActions(
                ofproto.OFPIT_APPLY_ACTIONS,
                actions
            )
        ]

        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=instructions,
            idle_timeout=idle_timeout,
            hard_timeout=0
        )

        datapath.send_msg(flow_mod)

        self.logger.info(
            "FLOW MOD SENT | Switch: %s | Priority: %s",
            datapath.id,
            priority
        )

    # -------------------------------------------------
    # OPENFLOW ERROR HANDLING
    # -------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPErrorMsg, MAIN_DISPATCHER)
    def openflow_error_handler(self, ev):
        msg = ev.msg
        self.logger.error(
            "OPENFLOW ERROR | Switch: %s | Type: %s | Code: %s",
            msg.datapath.id,
            msg.type,
            msg.code
        )


    def is_switch_port(self, dpid, port):

        for _, _, data in self.network.edges(dpid, data=True):
            if data["port"] == port:
                return True

        return False

    def learn_host(self, dpid, mac, port):

        if not self.is_switch_port(dpid, port):

            self.hosts[mac] = (dpid, port)

            self.logger.info(
                "HOST LEARNED | MAC: %s | Switch: %s | Port: %s",
                mac,
                dpid,
                port
            )

    # -------------------------------------------------
    # LOOP-FREE ARP BROADCAST
    # -------------------------------------------------

    def flood_arp(self, datapath, in_port, data, src_mac=None):
        """Flood ARP over a spanning tree to avoid loops on cyclic topologies."""
        dpid = datapath.id
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto

        if dpid not in self.network:
            self.logger.warning("ARP topology unavailable at switch %s", dpid)
            return

        # A spanning tree keeps broadcasts loop-free in the diamond while
        # still reaching hosts attached to intermediate switches (such as h3).
        tree = nx.minimum_spanning_tree(self.network.to_undirected())
        outputs = {
            port for port in self.switch_ports.get(dpid, {})
            if not self.is_switch_port(dpid, port)
        }

        for neighbor in tree.neighbors(dpid):
            edge = self.network.get_edge_data(dpid, neighbor)
            if edge and "port" in edge:
                outputs.add(edge["port"])
                continue

            # LLDP normally provides both directions. Use the reverse
            # discovery's destination port if only that direction is present.
            reverse_edge = self.network.get_edge_data(neighbor, dpid)
            if reverse_edge and "dst_port" in reverse_edge:
                outputs.add(reverse_edge["dst_port"])

        outputs.discard(in_port)

        if not outputs:
            self.logger.warning("ARP has no eligible output ports at switch %s", dpid)
            return

        actions = [parser.OFPActionOutput(port) for port in sorted(outputs)]
        datapath.send_msg(parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=data
        ))
        self.logger.info("LOOP-FREE ARP | Switch: %s | Outputs: %s",
                         dpid, sorted(outputs))

    # -------------------------------------------------
    # PATH CALCULATION
    # -------------------------------------------------

    def calculate_path(self, src_dpid, dst_dpid):
        try:
            if (src_dpid, dst_dpid) in ((1, 4), (4, 1)):

                if src_dpid == 1:
                    candidates = [
                        ("upper", [1, 2, 3, 4]),
                        ("lower", [1, 4])
                    ]
                else:
                    candidates = [
                        ("upper", [4, 3, 2, 1]),
                        ("lower", [4, 1])
                    ]

                # Try the configured path first, then its alternative.
                candidates.sort(
                    key=lambda item: item[0] != self.selected_path
                )

                for path_name, preferred in candidates:
                    available = all(
                        self.network.has_edge(
                            preferred[i], preferred[i + 1]
                        )
                        for i in range(len(preferred) - 1)
                    )

                    if available:
                        if path_name != self.selected_path:
                            old_path = self.selected_path
                            self.selected_path = path_name

                            self.logger.warning(
                                "PATH FAILOVER | %s -> %s",
                                old_path,
                                path_name
                            )

                        self.logger.info(
                            "SELECTED PATH | %s",
                            preferred
                        )

                        return preferred

            return nx.shortest_path(
                self.network,
                source=src_dpid,
                target=dst_dpid
            )

        except (nx.NetworkXNoPath, nx.NodeNotFound):
            self.logger.warning(
                "No path available between %s and %s",
                src_dpid,
                dst_dpid
            )
            return None

    # INSTALL ROUTE ON ALL SWITCHES
    # -------------------------------------------------

    def install_path(self, path, dst_mac, dst_port):

        for index, dpid in enumerate(path):

            datapath = self.datapaths.get(dpid)

            if datapath is None:
                return False

            parser = datapath.ofproto_parser

            if index == len(path) - 1:

                # Destination switch: forward to host
                out_port = dst_port

            else:

                next_switch = path[index + 1]

                out_port = self.network[dpid][next_switch]["port"]

            match = parser.OFPMatch(
                eth_dst=dst_mac
            )

            actions = [
                parser.OFPActionOutput(out_port)
            ]

            self.add_flow(
                datapath,
                priority=10,
                match=match,
                actions=actions
            )

            self.logger.info(
                "ROUTE INSTALLED | Switch: %s | Destination: %s | Output: %s",
                dpid,
                dst_mac,
                out_port
            )

        return True

    # -------------------------------------------------
    # PACKET-IN HANDLER
    # -------------------------------------------------

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath

        dpid = datapath.id
        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)

        eth = pkt.get_protocol(
            ethernet.ethernet
        )

        if eth is None:
            return

        # Ignore LLDP
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src_mac = eth.src
        dst_mac = eth.dst

        # Ignore IPv6 multicast and other multicast traffic
        if dst_mac.startswith("33:33:"):
            return

        # Learn the source host
        self.learn_host(
            dpid,
            src_mac,
            in_port
        )

        # Handle ARP broadcasts using spanning tree
        if dst_mac == "ff:ff:ff:ff:ff:ff":

            self.flood_arp(
                datapath,
                in_port,
                msg.data,
                src_mac=src_mac
            )

            return

        # Look up destination host
        destination = self.hosts.get(dst_mac)

        if destination is None:
            self.logger.info(
                "Destination not learned yet: %s",
                dst_mac
            )
            return

        dst_dpid, dst_port = destination

        # Same-switch forwarding
        if dpid == dst_dpid:

            path = [dpid]

        else:

            path = self.calculate_path(
                dpid,
                dst_dpid
            )

        if not path:
            return

        # Install route on every switch
        if not self.install_path(
            path,
            dst_mac,
            dst_port
        ):
            return

        # Forward the current packet
        if len(path) == 1:
            out_port = dst_port
        else:
            out_port = self.network[dpid][path[1]]["port"]

        actions = [
            datapath.ofproto_parser.OFPActionOutput(out_port)
        ]

        out = datapath.ofproto_parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=datapath.ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )

        datapath.send_msg(out)

        self.logger.info(
            "PACKET FORWARDED | Path: %s | Destination: %s",
            path,
            dst_mac
        )
