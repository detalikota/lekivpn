import re
import sys
sys.path.append('/opt/marzban')
from cred import API_TOKEN
import paramiko
import telebot
from collections import defaultdict
import ipaddress
import json
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vpnbot-block.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Config
LOG_FILE = '/var/log/remote/logs'
TELEGRAM_BOT_TOKEN = API_TOKEN
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def load_servers():
    try:
        with open('/opt/marzban/servers.json', 'r') as f:
            data = json.load(f)
            servers = data['servers']
            logger.info(f"Loaded {len(servers)} servers from config")
            return servers
    except Exception as e:
        logger.error(f"Failed to load servers config: {e}")
        return []

def get_network_24(ip):
    return str(ipaddress.ip_network(f'{ip}/24', strict=False))

def parse_log_entries():
    user_ips = defaultdict(list)
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            logger.info(f"Processing {len(lines)} log entries")
            
            for line_num, line in enumerate(lines, 1):
                try:
                    ip = re.search(r'from (\d+\.\d+\.\d+\.\d+)', line).group(1)
                    user_id = re.search(r'email: \d+\.(\w+)', line).group(1)
                    
                    network_24 = get_network_24(ip)
                    current_networks = {entry['network_24'] for entry in user_ips[user_id]}
                    if network_24 not in current_networks:
                        user_ips[user_id].append({
                            'ip': ip,
                            'network_24': network_24
                        })
                except:
                    continue
            
            logger.info(f"Parsed {len(user_ips)} unique users with IPs")
            for user_id, ips in user_ips.items():
                if len(ips) > 3:
                    logger.warning(f"User {user_id} has {len(ips)} different networks: {[ip['network_24'] for ip in ips]}")
                    
    except Exception as e:
        logger.error(f"Failed to parse log entries: {e}")
    
    return user_ips

def is_ip_in_range(ip):
    ip_parts = list(map(int, ip.split('.')))
    ip_int = (ip_parts[0] << 24) + (ip_parts[1] << 16) + (ip_parts[2] << 8) + ip_parts[3]
    
    start = (188 << 24) + (170 << 16) + (168 << 8) + 0
    end = (188 << 24) + (170 << 16) + (175 << 8) + 255
    
    in_range = start <= ip_int <= end
    logger.info(f"IP {ip} in range check: {in_range}")
    return in_range

def block_ip(ip, servers):
    blocked_servers = 0
    failed_servers = 0
    
    logger.info(f"Starting IP block for {ip} on {len(servers)} servers")
    
    for server in servers:
        server_host = server['host']
        try:
            logger.info(f"Connecting to server {server_host}")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                server['host'],
                username=server['user'],
                password=server['password'],
                timeout=10
            )
            
            commands = [
                f'ufw prepend deny from {ip} to any',
                f'(sleep 600 && ufw delete deny from {ip} to any) &'
            ]
            
            for cmd in commands:
                logger.debug(f"Executing on {server_host}: {cmd}")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    error_output = stderr.read().decode()
                    logger.warning(f"Command failed on {server_host}: {error_output}")
            
            blocked_servers += 1
            logger.info(f"Successfully blocked {ip} on {server_host}")
            
        except Exception as e:
            failed_servers += 1
            logger.error(f"Failed to connect/block on {server_host}: {e}")
        finally:
            try:
                ssh.close()
            except:
                pass
    
    logger.info(f"Block operation completed: {blocked_servers} successful, {failed_servers} failed")

def notify_user(user_id, ip):
    try:
        logger.info(f"Sending notification to user {user_id} about blocked IP {ip}")
        message = f"⛔️Уважаемый пользователь, следующий айпи-адрес: {ip} был заблокирован на 10 минут из-за превышения лимита одновременных активных устройств. Просьба не передавать VPN-конфигурацию третьим лицам ⛔️"
        result = bot.send_message(user_id, message)
        logger.info(f"Telegram notification sent successfully to {user_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification to {user_id}: {e}")

def main():
    logger.info("=== VPN Bot Block Script Started ===")
    
    servers = load_servers()
    if not servers:
        logger.error("No servers loaded, exiting")
        return
    
    user_ips = parse_log_entries()
    if not user_ips:
        logger.info("No user IPs found, nothing to process")
        return
    
    actions_taken = 0
    for user_id, ips in user_ips.items():
        if len(ips) > 3:
            ip_to_block = ips[-1]['ip']
            logger.warning(f"User {user_id} exceeded limit with {len(ips)} networks, blocking {ip_to_block}")
            
            if not is_ip_in_range(ip_to_block):
                block_ip(ip_to_block, servers)
                notify_user(user_id, ip_to_block)
                actions_taken += 1
            else:
                logger.info(f"Skipping IP {ip_to_block} - in allowed range")
    
    logger.info(f"=== Script Completed - {actions_taken} actions taken ===")

if __name__ == '__main__':
    main()
