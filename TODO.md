* fix not properly reporting 'playback-stopped' events to PMS/PlexWebClient
* serve local cached item to xbmc instead of directing it to local file:// uri
* proper empty dirs cleanup in PlexStorageManager
* save all the required info to metadata.json in order to re-build LocalSyncItem() objects
* save the metadata.json in ONE centralized file to remove the need to walk on the entire file tree just for the jsons..
* PIN code signin instead of SAVING THE PASSWORD TO DISK (!)
* fix invalid (?) playQueue
* Subtitle support (find out how to set subtitle via jsonrpc. last resort: tiny xbmc plugin to allow it??)