from .jellyfin import Jellyfin
from .jellyfin.connection_manager import CONNECTION_STATE
from .jellyfin.exceptions import HTTPException
from .conf import settings
from . import conffile
from getpass import getpass

import sys
import os.path
import json

CLIENT_VERSION = "1.0.0"
APP_NAME = 'jellyfin-mpv-shim'

CONNECTION_STATE = {
    'Unavailable': 0,
    'ServerSelection': 1,
    'ServerSignIn': 2,
    'SignedIn': 3
}

class ClientManager(object):
    def __init__(self):
        self.default_client = None
        self.callback = lambda client, event_name, data: None
    
    def connect(self):
        credentials = None
        credentials_location = conffile.get(APP_NAME,'cred.json')
        if os.path.exists(credentials_location):
            with open(credentials_location) as cf:
                credentials = json.load(cf)

        client = Jellyfin(None)
        client.config.data['app.default'] = True
        client.config.app(APP_NAME, CLIENT_VERSION, settings.player_name, settings.client_uuid)
        client.config.data['http.user_agent'] = "Jellyfin-MPV-Shim/%s" % CLIENT_VERSION
        client.config.data['auth.ssl'] = not settings.allow_http

        is_logged_in = False

        if credentials is not None:
            state = client.authenticate(credentials)
            is_logged_in = state['State'] == CONNECTION_STATE['SignedIn']

        if len(sys.argv) > 1 and sys.argv[1] == "add":
            is_logged_in = False

        while not is_logged_in:
            server = input("Server URL: ")
            username = input("Username: ")
            password = getpass("Password: ")
            client.auth.connect_to_address(server)
            client.auth.login(server, username, password)
            state = client.auth.connect()
            is_logged_in = state['State'] == CONNECTION_STATE['SignedIn']
            if is_logged_in:
                credentials = client.auth.credentials.get_credentials()
                with open(credentials_location, "w") as cf:
                    json.dump(credentials, cf)
                client.authenticate(credentials)

            add_another = input("Add another server? [y/N] ")
            if add_another in ("y", "Y", "yes", "Yes"):
                is_logged_in = False
        
        self.default_client = client

        clients = self.default_client.get_active_clients()
        for name, client in clients.items():
            def event(event_name, data):
                self.callback(client, event_name, data)

            client.callback = event
            client.callback_ws = event
            client.start(websocket=True)

            client.jellyfin.post_capabilities({
                'PlayableMediaTypes': "Video",
                'SupportsMediaControl': True,
                'SupportedCommands': (
                    "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                    "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                    "GoHome,PageUp,NextLetter,GoToSearch,"
                    "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                    "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                    "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                    "SetRepeatMode,"
                    "Mute,Unmute,SetVolume,"
                    "Play,Playstate,PlayNext,PlayMediaSource"
                ),
            })

    def stop(self):
        clients = self.default_client.get_active_clients()
        for _, client in clients.items():
            client.stop()

clientManager = ClientManager()
