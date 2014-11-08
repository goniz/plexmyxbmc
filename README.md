PlexMyXBMC
==========

Dependencies:

	* Python 2.7.*
	* plexapi:
			hg clone https://bitbucket.org/mjs7232/plexapi
	        sudo pip install ./plexapi
	* Plex Media Server on LAN + Plex Account
	* XBMC on LAN - HTTP Server enabled

Configuration:

	Configuration file resides in ${HOME}/.plexmyxbmc.json
	Populate the configuration file using genconfig.py as follows:

    ./genconfig.py --xbmc-host localhost --xbmc-port 8080
    ./genconfig.py --xbmc-username xbmc --xbmc-password xbmc
    ./genconfig.py --plex-username MYUSERNAME --plex-password MYPLEXPASS
    ./genconfig.py --name "Living Room XBMC"
    ./genconfig.py --display

CLI Usage:

	* run as your user or a dedicated user
    * no root needed
    
	./plexmyxbmc.py --foreground
	
	or
	
	./plexmyxbmc.py --daemon

API Usage:
	
    from plexmyxbmc.client import PlexClient

	client = PlexClient()
	client.serve()

	client.stop()
	client.join()