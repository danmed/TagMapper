# TagMapper

A Dockerized web app that synchronizes specific tags and labels from Plex to a Jellyfin server. 

If you use Plex to manage metadata tags (like "Kids" or "Anime") and want to apply those same tags to your Jellyfin library, this tool provides a local web interface to link the items, save them to a database, and keep them synced.

## Features

* **Multi-Label Support:** Create and manage separate JSON databases based on different labels. Switch between them using the dropdown menu.
* **Background Sync:** A background thread runs every 12 hours to verify the databases and re-apply tags to Jellyfin, protecting against metadata refreshes.
* **Batch Re-Apply:** Includes a batch tagging tool with a progress bar that processes items sequentially to prevent browser freezing.
* **Database Cleanup:** A "Clean Dead Links" tool scans the server and removes database entries for shows that no longer exist on Jellyfin.
* **Security:** The web interface and backend API are protected by HTTP Basic Authentication.
* **Optimized Search:** Uses server-side filtering on the Plex API to load pending lists quickly, even with large libraries.

---

## Installation (Docker)

The `docker-compose.yml` file is not included in the repository to prevent accidental credential commits. You will need to create it locally.

### 1. Clone the Repository
```bash
git clone https://github.com/danmed/TagMapper.git
cd EagMapper
```

### 2. Create the Configuration File
Create a new compose file on your server:
```bash
nano docker-compose.yml
```

### 3. Edit the Configuration
Copy the template below into your file. Replace the placeholder IP addresses, API Tokens, and passwords with your details:

```yaml
version: '3.8'

services:
  plex-mapper:
    build: .
    container_name: plex-jellyfin-mapper
    ports:
      - "5000:5000"
    volumes:
      - ./data:/data
    environment:
      # Security Settings
      - APP_USERNAME=admin
      - APP_PASSWORD=your_secure_password_here

      # Plex Settings
      - PLEX_URL=http://192.168.1.100:3240)
      - PLEX_TOKEN=your_plex_token_here
      - PLEX_LIBRARY_NAME=TV

      # Jellyfin Settings
      - JELLYFIN_URL=http://192.168.1.100:8096
      - JELLYFIN_API_KEY=your_jellyfin_admin_api_key
      - JELLYFIN_USER_ID=your_jellyfin_admin_user_id

      # App Settings
      - TARGET_LABEL=DefaultLabel
      - SYNC_INTERVAL_HOURS=12
    restart: unless-stopped
```

### 4. Build and Launch
Build the Docker image and start the container:
```bash
docker compose up -d --build
```

### 5. Access the Web App
Open a web browser and navigate to `http://<your-server-ip>:5000`. Log in using the `APP_USERNAME` and `APP_PASSWORD` defined in your compose file.

---

## Usage Notes

* **Creating a New Label:** Click the "+ New Label" button to create a new database file. It will be added to the dropdown menu automatically.
* **Finding the Jellyfin User ID:** The User ID is located in the Jellyfin web interface URL when viewing a user profile in the Admin Dashboard. This must be an Admin user for the tagging API to function.
* **Updating the App:** To pull the latest code without overwriting your compose file, temporarily rename it:
```bash
  mv docker-compose.yml compose-backup.yml
  git pull
  mv compose-backup.yml docker-compose.yml
  docker compose up -d --build
  docker image prune -f
  ```
