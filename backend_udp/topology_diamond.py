from mininet.topo import Topo


class DiamondThreeHostTopo(Topo):
    """Rhombus topology with a third host attached to S2."""

    def build(self):
        h1 = self.addHost("h1", ip="10.0.0.1/24")
        h2 = self.addHost("h2", ip="10.0.0.2/24")
        h3 = self.addHost("h3", ip="10.0.0.3/24")

        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")
        s4 = self.addSwitch("s4")

        self.addLink(h1, s1)
        self.addLink(h2, s4)
        self.addLink(h3, s2)

        # Upper route: s1 -> s2 -> s3 -> s4
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s3, s4)

        # Lower route: direct s1 -> s4
        self.addLink(s1, s4)


topos = {
    "diamond3": lambda: DiamondThreeHostTopo()
}
