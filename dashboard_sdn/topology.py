from mininet.topo import Topo


class DiamondTopo(Topo):

    def build(self):

        # Create switches
        s1 = self.addSwitch('s1')
        s2 = self.addSwitch('s2')
        s3 = self.addSwitch('s3')
        s4 = self.addSwitch('s4')

        # Create hosts
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')

        # Connect hosts
        self.addLink(h1, s1)
        self.addLink(s4, h2)
        self.addLink(h3, s2)

        # Upper route: S1 -> S2 -> S3 -> S4
        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s3, s4)

        # Lower route: direct S1 -> S4
        self.addLink(s1, s4)


topos = {
    'diamond': lambda: DiamondTopo()
}
