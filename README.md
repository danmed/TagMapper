# Plex to Jellyfin Mapper 🎬

A lightweight, Dockerized web app that helps you synchronize specific tags/labels from Plex over to Jellyfin. 

If you use Plex to manage specific labels (like "Kids", "Anime", or "LauraTV") and want to easily apply those same tags to your Jellyfin library, this tool gives you a clean GUI to link them up, save them to a local database, and batch re-apply them whenever Jellyfin overwrites its metadata.

## Features
* 🔍 **Native Search:** Lightning-fast Jellyfin API integration.
* 💾 **Persistent Database:** Remembers what you've linked so you don't have to do it twice.
* 🏷️ **Multi-Label Support:** Type in any label context and manage different databases seamlessly.
* 🔄 **Batch Re-Apply:** One-click re-application of tags if a Jellyfin metadata refresh wipes them out.

## Installation (Docker)

1. Clone this repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/plex-jellyfin-mapper.git](https://github.com/YOUR_USERNAME/plex-jellyfin-mapper.git)
   cd plex-jellyfin-mapper
2. Create docker-compose.yml
   ```yaml
   services:
   plex-mapper:
    build: .
    container_name: plex-jellyfin-mapper
    ports:
      - "5000:5000"
    volumes:
      - ./data:/data
    environment:
      - APP_USERNAME=admin
      - APP_PASSWORD=password123
      - PLEX_URL=[http://192.168.2.203:32400](http://192.168.2.203:32400)
      - PLEX_TOKEN=your_plex_token_here
      - PLEX_LIBRARY_NAME=TV
      - JELLYFIN_URL=[http://192.168.2.202:8096](http://192.168.2.202:8096)
      - JELLYFIN_API_KEY=your_jellyfin_api_key_here
      - JELLYFIN_USER_ID=your_jellyfin_admin_user_id
      - TARGET_LABEL=LauraTV
    restart: unless-stopped

## Screenshots
<img width="2306" height="888" alt="image" src="https://github.com/user-attachments/assets/56f566be-0e2e-4bd9-b038-e142e707e695" />
<img width="2285" height="825" alt="image" src="https://github.com/user-attachments/assets/8382e4bc-38b8-48a9-ab76-01ceeae3aa4a" />
