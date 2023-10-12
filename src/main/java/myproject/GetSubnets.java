package myproject;

import inet.ipaddr.IPAddress;
import inet.ipaddr.IPAddressString;

import java.io.PrintStream;
import java.util.Iterator;
import java.util.TreeSet;

public class GetSubnets {

    public GetSubnets() {
    }

    public IPAddress[] adjustBlock(String original, int bitShift) {
        IPAddress subnet = new IPAddressString(original).getAddress();
        IPAddress newSubnets = subnet.setPrefixLength(subnet.getPrefixLength() +
                bitShift, false);
        TreeSet<IPAddress> subnetSet = new TreeSet<IPAddress>();
        Iterator<? extends IPAddress> iterator = newSubnets.prefixBlockIterator();
        iterator.forEachRemaining(subnetSet::add);
        IPAddress[] subnetArray = subnetSet.toArray(new IPAddress[0]);
        return subnetArray;
    }
}
