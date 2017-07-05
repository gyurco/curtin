from .releases import base_vm_classes as relbase
from .releases import centos_base_vm_classes as centos_relbase
from .test_network import TestNetworkBaseTestsAbs

import textwrap


class TestNetworkIPV6Abs(TestNetworkBaseTestsAbs):
    """ IPV6 complex testing.  The configuration exercises
        - ipv4 and ipv6 address on same interface
        - bonding in LACP mode
        - unconfigured subnets on bond
        - vlans over bonds
        - all IP is static
    """
    conf_file = "examples/network-ipv6-bond-vlan.yaml"
    collect_scripts = TestNetworkBaseTestsAbs.collect_scripts + [
        textwrap.dedent("""
        grep . -r /sys/class/net/bond0/ > sysfs_bond0 || :
        grep . -r /sys/class/net/bond0.108/ > sysfs_bond0.108 || :
        grep . -r /sys/class/net/bond0.208/ > sysfs_bond0.208 || :
        """)]


class CentosTestNetworkIPV6Abs(TestNetworkIPV6Abs):
    extra_kern_args = "BOOTIF=eth0-bc:76:4e:06:96:b3"
    collect_scripts = TestNetworkIPV6Abs.collect_scripts + [
        textwrap.dedent("""
            cd OUTPUT_COLLECT_D
            cp -a /etc/sysconfig/network-scripts .
            cp -a /var/log/cloud-init* .
            cp -a /var/lib/cloud ./var_lib_cloud
            cp -a /run/cloud-init ./run_cloud-init
        """)]

    def test_etc_network_interfaces(self):
        pass

    def test_etc_resolvconf(self):
        pass


class PreciseHWETTestNetwork(relbase.precise_hwe_t, TestNetworkIPV6Abs):
    # FIXME: off due to hang at test: Starting execute cloud user/final scripts
    __test__ = False


class TrustyTestNetworkIPV6(relbase.trusty, TestNetworkIPV6Abs):
    __test__ = True


class TrustyHWEVTestNetworkIPV6(relbase.trusty_hwe_v, TrustyTestNetworkIPV6):
    # Working, off by default to safe test suite runtime, covered by bonding
    __test__ = False


class TrustyHWEWTestNetworkIPV6(relbase.trusty_hwe_w, TrustyTestNetworkIPV6):
    # Working, off by default to safe test suite runtime, covered by bonding
    __test__ = False


class TrustyHWEXTestNetworkIPV6(relbase.trusty_hwe_x, TrustyTestNetworkIPV6):
    # Working, off by default to safe test suite runtime, covered by bonding
    __test__ = False


class XenialTestNetworkIPV6(relbase.xenial, TestNetworkIPV6Abs):
    __test__ = True

    @classmethod
    def test_ip_output(cls):
        cls.skip_by_date(cls.__name__, cls.release, "1701097",
                         (2017, 7, 10), (2017, 7, 31))

class YakketyTestNetworkIPV6(relbase.yakkety, TestNetworkIPV6Abs):
    __test__ = True


class ZestyTestNetworkIPV6(relbase.zesty, TestNetworkIPV6Abs):
    __test__ = True


class ArtfulTestNetworkIPV6(relbase.artful, TestNetworkIPV6Abs):
    __test__ = True

    @classmethod
    def test_ip_output(cls):
        cls.skip_by_date(cls.__name__, cls.release, "1701097",
                         (2017, 7, 10), (2017, 7, 31))


class Centos66TestNetworkIPV6(centos_relbase.centos66fromxenial,
                              CentosTestNetworkIPV6Abs):
    __test__ = True


class Centos70TestNetworkIPV6(centos_relbase.centos70fromxenial,
                              CentosTestNetworkIPV6Abs):
    __test__ = True
