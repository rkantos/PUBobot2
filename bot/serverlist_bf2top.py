import requests
import socket


import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ["API_KEY"]

class BF2TopFetch:

    API_KEY = API_KEY

    def __init__(self, auto_load=True):
        """Initialize with a hardcoded API key and optionally load servers."""
        self.api_key = self.API_KEY
        self.servers = []  # Last successfully fetched server list
        self.city_data = []  # Last successfully fetched city data
        self.bf2_servers = []  # Converted BF2 server list
        
        if auto_load:
            self.load_servers()  # Automatically fetch and store server data

    def get_server_data(self):
        """Fetch server data from the API."""
        url = 'https://api.bf2.top/servers/rcons'
        headers = {'X-API-KEY': self.api_key}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            self.servers = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching server data: {e}")
            print("Using previously loaded server data.")
        return self.servers

    def get_city_data(self):
        """Fetch city names and their associated servers."""
        url = 'https://api.bf2.top/servers/'
        headers = {'X-API-KEY': self.api_key}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            self.city_data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching city data: {e}")
            print("Using previously loaded city data.")
        return self.city_data

    def convert_json_to_bf2_server_list(self):
        """Convert JSON data to a BF2 server list."""
        city_map = {server["address"]: server["name"] for server in self.city_data}
        self.bf2_servers = []  # Reset previous server list

        for entry in self.servers:
            hostname = entry.get("hostname", entry["id"])
            server_name = city_map.get(hostname, "Unknown Server")

            server = {
                "ip": "",
                "hostname": hostname,
                "name": server_name,
                "bf2port": 16567,
                "port": entry["rcon_port"],
                "rcon_password": entry["rcon_pw"],
                "jsport": 1025,
                "restarted": False
            }
            self.bf2_servers.append(server)

        # Resolve IP addresses
        for server in self.bf2_servers:
            try:
                server['ip'] = socket.getaddrinfo(server['hostname'], 0)[0][4][0]
            except socket.gaierror:
                print(f"Could not resolve IP for {server['hostname']}")

        return self.bf2_servers

    def load_servers(self):
        """Fetch all data and return the latest server list."""
        self.get_server_data()
        self.get_city_data()
        return self.convert_json_to_bf2_server_list()

    def get_bf2_servers(self):
        """Return the current server list without reloading."""
        return self.bf2_servers
