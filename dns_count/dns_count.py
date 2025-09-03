import re
import socket
from collections import Counter
from prometheus_client import start_http_server, Gauge
import time
import dns.resolver
from dns.resolver import NXDOMAIN
import ipaddress

class DomainMetricsCollector:
    def __init__(self):
        self.domain_gauges = {}
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 1
        self.resolver.lifetime = 1

    def get_domain_from_ip(self, ip):
        try:
            if '[' in ip:  # IPv6
                ip = ip.strip('[]')
            return socket.getnameinfo((ip, 0), 0)[0]
        except:
            return None  # Return None if DNS resolution fails

    def is_ip_address(self, addr):
        try:
            ipaddress.ip_address(addr.strip('[]'))
            return True
        except ValueError:
            return False

    def parse_log_line(self, line):
        match = re.search(r'accepted tcp:([^:\s]+)', line)
        if match:
            dest = match.group(1)
            return dest
        return None

    def process_logs(self):
        domains_counter = Counter()
        
        print("Processing logs...")
        with open('/var/log/remote/logs', 'r') as f:
            for line in f:
                dest = self.parse_log_line(line)
                if dest:
                    if self.is_ip_address(dest):
                        domain = self.get_domain_from_ip(dest)
                        if domain is None:  # Skip if DNS resolution failed
                            continue
                    else:
                        domain = dest
                    domains_counter[domain] += 1

        # Print top 15 domains for debugging
        print("\nTop 15 most accessed domains:")
        for domain, count in domains_counter.most_common(15):
            print(f"{domain}: {count} requests")

        # Update Prometheus metrics
        for domain, count in domains_counter.most_common(15):
            gauge_name = f'DNS_name_{re.sub("[^a-zA-Z0-9]", "_", domain)}'
            if domain not in self.domain_gauges:
                self.domain_gauges[domain] = Gauge(
                    gauge_name,
                    f'Number of requests to {domain}'
                )
            self.domain_gauges[domain].set(count)
        
        # Clear old metrics that are no longer in top 15
        current_top_domains = set(domain for domain, _ in domains_counter.most_common(15))
        for domain in list(self.domain_gauges.keys()):
            if domain not in current_top_domains:
                self.domain_gauges[domain]._metrics.clear()
                del self.domain_gauges[domain]

def main():
    print("Starting DNS metrics collector on port 8009...")
    start_http_server(8009)
    collector = DomainMetricsCollector()
    
    while True:
        try:
            collector.process_logs()
        except Exception as e:
            print(f"Error processing logs: {e}")
        print("\nWaiting 300 seconds before next update...")
        time.sleep(300)  # Update every 5 minutes

if __name__ == '__main__':
    main()