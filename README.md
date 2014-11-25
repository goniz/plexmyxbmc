PlexMyXBMC
==========

Description:

    PlexMyXBMC lets you use your existing XBMC Player as a fully working Plex client.
    Control your XBMC with the Android Plex App, iOS Plex App, Plex Web Client and any other plex controller.
    for example, login to Plex Web App and choose "Cast to PlexMyXBMC"
    then go browse your library on the web app and finally choose your movie/episode/etc.. and click play
    now your chosen media is playing on your XBMC player directly from the Plex Media Server !
    Currently does not support transcoding, playqueues or playlists
	
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

	run as your user or a dedicated user
    no root needed
    
	./plexmyxbmc.py
	
As Service:

    Customize and use the appropriate init script
    * initscripts/plexmyxbmc.initd   --> /etc/init.d/plexmyxbmc
        sudo cp initscripts/plexmyxbmc.initd /etc/init.d/plexmyxbmc
        sudo chmod +x /etc/init.d/plexmyxbmc
        sudo update-rc.d plexmyxbmc defaults
        sudo service plexmyxbmc start
    * initscripts/plexmyxbmc.service --> /usr/lib/systemd/system/plexmyxbmc.service
        sudo cp initscripts/plexmyxbmc.service /usr/lib/systemd/system/plexmyxbmc.service
        sudo systemctl daemon-reload
        sudo systemctl enable plexmyxbmc
        sudo systemctl start plexmyxbmc

API Usage:
	
    from plexmyxbmc.client import PlexClient

	client = PlexClient()
	client.serve()

	client.stop()
	client.join()
