import requests
import json
import os
import time
import threading
from functools import wraps
from flask import Flask, jsonify, request, render_template_string, Response
from plexapi.server import PlexServer

# --- CONFIGURATION (Docker Ready!) ---
PLEX_URL = os.getenv('PLEX_URL', 'http://192.168.2.203:32400')
PLEX_TOKEN = os.getenv('PLEX_TOKEN', 'YOUR_PLEX_TOKEN')
PLEX_LIBRARY_NAME = os.getenv('PLEX_LIBRARY_NAME', 'TV')

JELLYFIN_URL = os.getenv('JELLYFIN_URL', 'http://192.168.2.202:8096') 
JELLYFIN_API_KEY = os.getenv('JELLYFIN_API_KEY', 'YOUR_JELLYFIN_KEY')
JELLYFIN_USER_ID = os.getenv('JELLYFIN_USER_ID', 'YOUR_ADMIN_ID') 

DATA_DIR = os.getenv('DATA_DIR', '/data')
DEFAULT_LABEL = os.getenv('TARGET_LABEL', 'LauraTV')
SYNC_INTERVAL_HOURS = int(os.getenv('SYNC_INTERVAL_HOURS', '12')) # Background sync frequency

# --- SECURITY CREDENTIALS ---
APP_USERNAME = os.getenv('APP_USERNAME', 'admin')
APP_PASSWORD = os.getenv('APP_PASSWORD', 'password123')
# -------------------------------------

app = Flask(__name__)

# --- BACKGROUND AUTO-PILOT TASK ---
def auto_pilot_sync():
    """Runs continuously in the background, checking all databases every X hours."""
    while True:
        # Sleep first so it doesn't instantly slam the API on container boot
        time.sleep(SYNC_INTERVAL_HOURS * 3600) 
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Running Auto-Pilot Background Sync...")
        
        try:
            if not os.path.exists(DATA_DIR): continue
            
            headers = {
                'X-MediaBrowser-Token': JELLYFIN_API_KEY, 
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Loop through every label database we have
            for filename in os.listdir(DATA_DIR):
                if filename.endswith("_mapped_shows.json"):
                    label = filename.replace("_mapped_shows.json", "")
                    if not label or label == "default": continue
                    
                    db_path = os.path.join(DATA_DIR, filename)
                    with open(db_path, 'r') as f:
                        try:
                            matches = json.load(f)
                        except:
                            continue
                            
                    # Re-apply the specific label to every item in the database
                    for match in matches:
                        j_id = match.get('jellyfin_id')
                        if not j_id: continue
                        
                        detail_url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items/{j_id}"
                        res = requests.get(detail_url, headers=headers)
                        
                        if res.status_code == 200:
                            item_data = res.json()
                            tags = item_data.get('Tags', [])
                            if label not in tags:
                                tags.append(label)
                                item_data['Tags'] = tags
                                requests.post(f"{JELLYFIN_URL}/Items/{j_id}", headers=headers, json=item_data)
                                
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Auto-Pilot Sync Complete.")
        except Exception as e:
            print(f"Auto-Pilot Sync Error: {e}")

# --- AUTHENTICATION LOGIC ---
def check_auth(username, password):
    return username == APP_USERNAME and password == APP_PASSWORD

def authenticate():
    return Response(
        'Authentication required to access the Mapper.\n', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- DATABASE FUNCTIONS ---
def get_db_file(label):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
        
    safe_label = "".join(c for c in label if c.isalnum())
    if not safe_label:
        safe_label = "default"
    return os.path.join(DATA_DIR, f"{safe_label}_mapped_shows.json")

def load_mapped_shows(label):
    db_file = get_db_file(label)
    if os.path.exists(db_file):
        with open(db_file, 'r') as f:
            try:
                return json.load(f)
            except:
                return []
    return []

def save_mapped_show(plex_id, jellyfin_id, title, label):
    mapped = load_mapped_shows(label)
    if not any(str(m.get('plex_id')) == str(plex_id) for m in mapped):
        mapped.append({"plex_id": plex_id, "jellyfin_id": jellyfin_id, "title": title})
        with open(get_db_file(label), 'w') as f:
            json.dump(mapped, f, indent=4)

def remove_mapped_show(plex_id, label):
    mapped = load_mapped_shows(label)
    mapped = [m for m in mapped if str(m.get('plex_id')) != str(plex_id)]
    with open(get_db_file(label), 'w') as f:
        json.dump(mapped, f, indent=4)

# --- HTML & JAVASCRIPT FRONTEND ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Multi-Label Plex to Jellyfin Mapper</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121212; color: #fff; margin: 0; padding: 20px; display: flex; flex-direction: column; height: 100vh; box-sizing: border-box; }
        
        .label-bar { display: flex; align-items: center; gap: 15px; background: #1e1e1e; padding: 15px 20px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #00a4dc; }
        .label-bar select { padding: 10px; border-radius: 4px; border: none; background: #2c2c2c; color: #fff; font-size: 16px; font-weight: bold; width: 250px; cursor: pointer;}
        .label-bar button { padding: 10px 20px; background: #00a4dc; color: #fff; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 16px; }
        .label-bar button:hover { background: #00bfff; }

        .tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .tab-btn { background: #2c2c2c; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; }
        .tab-btn.active { background: #e5a00d; color: #000; }
        .tab-content { display: none; flex: 1; gap: 20px; overflow: hidden; }
        .tab-content.active { display: flex; }
        
        .column { flex: 1; background: #1e1e1e; border-radius: 8px; padding: 20px; display: flex; flex-direction: column; overflow: hidden; }
        h2 { margin-top: 0; color: #e5a00d; }
        .list-container { overflow-y: auto; flex: 1; color: #aaa; font-style: italic; }
        .item { background: #2c2c2c; margin-bottom: 10px; padding: 15px; border-radius: 6px; cursor: pointer; transition: 0.2s; border: 2px solid transparent; color: #fff; font-style: normal; }
        .item:hover { background: #3d3d3d; }
        .item.active { border-color: #e5a00d; background: #3d3d3d; }
        
        .search-box { display: flex; gap: 10px; margin-bottom: 20px; }
        input[type="text"] { flex: 1; padding: 10px; border-radius: 4px; border: none; background: #2c2c2c; color: #fff; font-size: 16px; }
        button.action-btn { padding: 10px 20px; background: #e5a00d; color: #000; border: none; border-radius: 4px; font-weight: bold; cursor: pointer; font-size: 16px; }
        button.action-btn:hover { background: #ffb822; }
        
        .jf-result { display: flex; gap: 15px; background: #2c2c2c; padding: 15px; border-radius: 6px; margin-bottom: 10px; align-items: center; color: #fff; font-style: normal; }
        .jf-result img { width: 50px; height: 75px; object-fit: cover; border-radius: 4px; background: #444; }
        .jf-info { flex: 1; }
        .tag-btn { background: #00a4dc; color: #fff; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;}
        .tag-btn:hover { background: #00bfff; }
        
        .del-btn { background: #d32f2f; color: #fff; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; margin-left: auto;}
        .del-btn:hover { background: #f44336; }
        .sort-btn { background: #444; color: #fff; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;}
        .sort-btn:hover { background: #555; }
        
        .success-msg { color: #4caf50; font-weight: bold; display: none; margin-bottom: 15px; }

        .db-item { display: flex; align-items: center; gap: 15px; background: #2c2c2c; padding: 10px 15px; margin-bottom: 8px; border-radius: 6px; color: #fff; font-style: normal; }
        .db-item input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
        .db-item img { width: 50px; height: 75px; object-fit: cover; border-radius: 4px; background: #444; }
        .db-toolbar { display: flex; gap: 15px; margin-bottom: 15px; align-items: center; background: #1e1e1e; padding: 15px; border-radius: 8px;}
        .db-status { color: #aaa; margin-left: auto; font-style: italic; }
    </style>
</head>
<body>

    <div class="label-bar">
        <span><strong>Active Label:</strong></span>
        <select id="globalLabel" onchange="changeLabel()"></select>
        <button onclick="createNewHtmlLabel()" style="background: #444;">+ New Label</button>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('mapper')" id="tab-mapper">1. Match New Shows</button>
        <button class="tab-btn" onclick="switchTab('database')" id="tab-database">2. Saved Database & Re-Apply</button>
    </div>

    <div id="mapper" class="tab-content active">
        <div class="column">
            <h2>Select Plex Show</h2>
            <p>Pending shows in Plex with label: <strong id="displayLabel">None Loaded</strong></p>
            <div class="list-container" id="plexList">Loading...</div>
        </div>
        <div class="column">
            <h2>Match in Jellyfin</h2>
            <div class="search-box">
                <input type="text" id="jfSearch" placeholder="Search Jellyfin...">
                <button class="action-btn" onclick="searchJellyfin()">Search</button>
            </div>
            <div class="success-msg" id="successMsg">✨ Tag applied and saved to database!</div>
            <div class="list-container" id="jfList">Select a Plex show first.</div>
        </div>
    </div>

    <div id="database" class="tab-content" style="flex-direction: column;">
        <div class="db-toolbar">
            <button class="action-btn" onclick="selectAllDB()">Select All</button>
            <button class="action-btn" onclick="deselectAllDB()">Deselect All</button>
            <button class="tag-btn" id="reapplyBtn" onclick="reapplySelected()">Re-Apply Tags to Selected</button>
            
            <button class="action-btn" id="cleanBtn" onclick="cleanupDatabase()" style="background: #8b5cf6; color: white;">🧹 Clean Dead Links</button>
            
            <button id="sortBtn" class="sort-btn" onclick="toggleSort()">Sort: A-Z ↓</button>
            
            <progress id="reapplyProgress" value="0" max="100" style="display: none; margin-left: auto; width: 150px; accent-color: #e5a00d;"></progress>
            
            <div class="db-status" id="dbStatus"></div>
        </div>
        <div class="list-container" id="dbList" style="background: #1e1e1e; border-radius: 8px; padding: 20px;">
            Select a label to view its saved database.
        </div>
    </div>

    <script>
        let currentPlexShow = null;
        let cachedDbData = [];
        let dbSortOrder = 'asc'; 
        let activeTab = 'mapper'; 
        let hasLoaded = false; 
        
        // We pass the Jellyfin URL from Python to Javascript so it can load the images!
        const jfUrl = "{{ jellyfin_url }}";

        function loadKnownLabels(targetSelectValue = null) {
            fetch('/api/known_labels')
                .then(res => res.json())
                .then(labels => {
                    const select = document.getElementById('globalLabel');
                    const currentSelection = targetSelectValue || select.value || "{{ default_label }}";
                    
                    select.innerHTML = ''; 
                    labels.forEach(label => {
                        let option = document.createElement('option');
                        option.value = label;
                        option.innerText = label;
                        if (label === currentSelection) option.selected = true;
                        select.appendChild(option);
                    });
                    
                    if (!hasLoaded) {
                        changeLabel();
                    }
                })
                .catch(err => console.error("Error loading known labels:", err));
        }

        async function createNewHtmlLabel() {
            let newLabel = prompt("Enter new label name (Letters and numbers only):");
            if (!newLabel) return;
            
            newLabel = newLabel.replace(/[^a-zA-Z0-9]/g, ""); 
            if (!newLabel) return alert("Invalid label name!");
            
            try {
                await fetch('/api/create_label', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ label: newLabel })
                });

                loadKnownLabels(newLabel);
                setTimeout(() => changeLabel(), 50);
            } catch (err) {
                alert("Failed to create label database.");
            }
        }

        function getActiveLabel() {
            return document.getElementById('globalLabel').value;
        }

        function changeLabel() {
            let label = getActiveLabel();
            if(!label) return;
            
            hasLoaded = true; 
            document.getElementById('displayLabel').innerText = label;
            document.getElementById('successMsg').style.display = 'none';
            document.getElementById('jfList').innerHTML = 'Select a Plex show first.';
            currentPlexShow = null;

            if (activeTab === 'mapper') {
                loadPlexShows();
            } else {
                loadDatabase();
            }
        }

        function switchTab(tabId) {
            activeTab = tabId;
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
            
            if (hasLoaded) {
                if(tabId === 'database') loadDatabase();
                if(tabId === 'mapper') loadPlexShows();
            }
        }

        function loadPlexShows() {
            let label = getActiveLabel();
            document.getElementById('plexList').innerHTML = 'Loading from Plex...';
            
            fetch(`/api/plex_shows?label=${encodeURIComponent(label)}`)
                .then(res => res.json())
                .then(data => {
                    const list = document.getElementById('plexList');
                    list.innerHTML = '';
                    if(data.error) { list.innerHTML = `<p style="color:red">${data.error}</p>`; return; }
                    if(data.length === 0) { list.innerHTML = '<p style="color:#4caf50">🎉 All caught up! No pending shows for this label.</p>'; return; }
                    
                    data.forEach(show => {
                        const div = document.createElement('div');
                        div.className = 'item';
                        div.id = `plex-${show.id}`;
                        div.innerHTML = `<strong>${show.title}</strong> (${show.year || 'N/A'})`;
                        div.onclick = () => selectPlexShow(show, div);
                        list.appendChild(div);
                    });
                });
        }

        function selectPlexShow(show, element) {
            document.querySelectorAll('.item').forEach(el => el.classList.remove('active'));
            element.classList.add('active');
            currentPlexShow = show;
            
            let cleanTitle = show.title.split(' (')[0];
            document.getElementById('jfSearch').value = cleanTitle;
            document.getElementById('successMsg').style.display = 'none';
            searchJellyfin();
        }

        function searchJellyfin() {
            const query = document.getElementById('jfSearch').value;
            if(!query) return;
            
            const list = document.getElementById('jfList');
            list.innerHTML = 'Searching...';

            fetch(`/api/search_jellyfin?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    list.innerHTML = '';
                    if(data.length === 0) { list.innerHTML = '<p>No results found.</p>'; return; }
                    
                    data.forEach(item => {
                        const div = document.createElement('div');
                        div.className = 'jf-result';
                        div.innerHTML = `
                            <img src="${item.image_url}" alt="poster" onerror="this.src='https://via.placeholder.com/50x75?text=No+Img'">
                            <div class="jf-info">
                                <strong>${item.name}</strong> <small>(${item.type})</small><br>
                                <small>${item.year || 'Unknown Year'}</small>
                            </div>
                            <button class="tag-btn" onclick="applyTag('${item.id}')">Link & Tag</button>
                        `;
                        list.appendChild(div);
                    });
                });
        }

        function applyTag(jellyfinId) {
            if(!currentPlexShow) return alert("Select a Plex show first!");
            let label = getActiveLabel();
            
            fetch('/api/apply_tag', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    jellyfin_id: jellyfinId, 
                    plex_id: currentPlexShow.id, 
                    title: currentPlexShow.title,
                    label: label
                })
            })
            .then(res => res.json())
            .then(data => {
                if(data.success) {
                    document.getElementById('successMsg').style.display = 'block';
                    document.getElementById('jfList').innerHTML = '';
                    document.getElementById(`plex-${currentPlexShow.id}`).remove();
                    currentPlexShow = null;
                    loadKnownLabels(label);
                } else {
                    alert("Error: " + data.error);
                }
            });
        }

        function loadDatabase() {
            let label = getActiveLabel();
            document.getElementById('dbList').innerHTML = 'Loading database...';
            
            fetch(`/api/saved_matches?label=${encodeURIComponent(label)}&nocache=${new Date().getTime()}`)
                .then(res => res.json())
                .then(data => {
                    cachedDbData = data; 
                    renderDatabase();    
                });
        }

        function toggleSort() {
            dbSortOrder = (dbSortOrder === 'asc') ? 'desc' : 'asc';
            document.getElementById('sortBtn').innerText = (dbSortOrder === 'asc') ? 'Sort: A-Z ↓' : 'Sort: Z-A ↑';
            renderDatabase(); 
        }

        function renderDatabase() {
            const list = document.getElementById('dbList');
            list.innerHTML = '';
            if(cachedDbData.length === 0) { list.innerHTML = `<p>No saved shows yet for ${getActiveLabel()}.</p>`; return; }
            
            let sortedData = [...cachedDbData].sort((a, b) => {
                let titleA = (a.title || `Unknown Title (Plex ID: ${a.plex_id})`).toLowerCase();
                let titleB = (b.title || `Unknown Title (Plex ID: ${b.plex_id})`).toLowerCase();
                
                if(titleA < titleB) return dbSortOrder === 'asc' ? -1 : 1;
                if(titleA > titleB) return dbSortOrder === 'asc' ? 1 : -1;
                return 0;
            });

            // UPDATED: Now displays the Jellyfin poster next to each saved item!
            sortedData.forEach(item => {
                const div = document.createElement('div');
                div.className = 'db-item';
                let displayTitle = item.title ? item.title : `Unknown Title (Plex ID: ${item.plex_id})`;
                let imgUrl = `${jfUrl}/Items/${item.jellyfin_id}/Images/Primary?fillHeight=75&fillWidth=50&quality=80`;
                
                div.innerHTML = `
                    <input type="checkbox" class="db-checkbox" value="${item.jellyfin_id}">
                    <img src="${imgUrl}" alt="poster" onerror="this.src='https://via.placeholder.com/50x75?text=No+Img'">
                    <div class="jf-info">
                        <strong>${displayTitle}</strong>
                    </div>
                    <button class="del-btn" onclick="deleteMatch('${item.plex_id}', '${item.jellyfin_id}', this)">Unlink & Remove</button>
                `;
                list.appendChild(div);
            });
            
            document.getElementById('dbStatus').innerText = `${sortedData.length} matches in database`;
        }

        // NEW FEATURE: Health Check / Database Cleanup
        async function cleanupDatabase() {
            let label = getActiveLabel();
            if(!label) return;
            if(!confirm("This will scan Jellyfin and automatically remove any saved matches that have been deleted from your server. Continue?")) return;
            
            const cleanBtn = document.getElementById('cleanBtn');
            const originalText = cleanBtn.innerText;
            cleanBtn.innerText = "Scanning Server...";
            cleanBtn.style.background = "#555";
            cleanBtn.disabled = true;
            
            try {
                const response = await fetch('/api/cleanup_database', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ label: label })
                });
                const result = await response.json();
                
                if(result.success) {
                    alert(`Cleanup complete! Removed ${result.removed} dead links from the database.`);
                    loadDatabase();
                } else {
                    alert("Error: " + result.error);
                }
            } catch (err) {
                alert("Connection error.");
            }
            
            cleanBtn.innerText = originalText;
            cleanBtn.style.background = "#8b5cf6";
            cleanBtn.disabled = false;
        }

        async function deleteMatch(plexId, jellyfinId, buttonElement) {
            if(!confirm("Are you sure? This will remove the tag from Jellyfin and delete the link.")) return;
            
            const originalText = buttonElement.innerText;
            buttonElement.innerText = "Deleting...";
            buttonElement.style.background = "#555";
            buttonElement.disabled = true;
            let label = getActiveLabel();
            
            try {
                const response = await fetch('/api/delete_match', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ plex_id: plexId, jellyfin_id: jellyfinId, label: label })
                });
                const result = await response.json();
                
                if(result.success) {
                    loadDatabase(); 
                    loadKnownLabels(label); 
                } else {
                    alert("Error: " + result.error);
                    buttonElement.innerText = originalText;
                    buttonElement.style.background = "#d32f2f";
                    buttonElement.disabled = false;
                }
            } catch (err) {
                alert("Connection error.");
                buttonElement.innerText = originalText;
                buttonElement.disabled = false;
            }
        }

        function selectAllDB() {
            document.querySelectorAll('.db-checkbox').forEach(cb => cb.checked = true);
        }

        function deselectAllDB() {
            document.querySelectorAll('.db-checkbox').forEach(cb => cb.checked = false);
        }

        async function reapplySelected() {
            const checkboxes = document.querySelectorAll('.db-checkbox:checked');
            if(checkboxes.length === 0) return alert("Select at least one show to re-apply tags.");
            
            const jellyfinIds = Array.from(checkboxes).map(cb => cb.value);
            const statusDiv = document.getElementById('dbStatus');
            const progressBar = document.getElementById('reapplyProgress');
            const actionBtn = document.getElementById('reapplyBtn');
            let label = getActiveLabel();
            
            let total = jellyfinIds.length;
            let successCount = 0;
            
            actionBtn.disabled = true;
            actionBtn.style.background = "#555";
            actionBtn.innerText = "Applying...";
            
            progressBar.max = total;
            progressBar.value = 0;
            progressBar.style.display = "block";
            statusDiv.style.marginLeft = "15px";
            
            for (let i = 0; i < total; i++) {
                statusDiv.innerText = `Tagging: ${i + 1} / ${total}`;
                progressBar.value = i + 1;
                
                try {
                    const response = await fetch('/api/reapply_batch', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ jellyfin_ids: [jellyfinIds[i]], label: label })
                    });
                    const result = await response.json();
                    if(result.success) {
                        successCount += result.count;
                    }
                } catch (err) {
                    console.error("Failed to tag ID: " + jellyfinIds[i]);
                }
            }

            progressBar.style.display = "none";
            actionBtn.disabled = false;
            actionBtn.style.background = "#00a4dc";
            actionBtn.innerText = "Re-Apply Tags to Selected";
            statusDiv.style.marginLeft = "auto";
            
            statusDiv.innerHTML = `<span style="color:#4caf50">✅ Successfully tagged ${successCount} out of ${total} items!</span>`;
            setTimeout(() => deselectAllDB(), 1500);
        }

        document.addEventListener('DOMContentLoaded', () => loadKnownLabels());
    </script>
</body>
</html>
"""

# --- BACKEND API ROUTES ---

def get_jf_headers():
    return {
        'X-MediaBrowser-Token': JELLYFIN_API_KEY, 
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

@app.route('/')
@requires_auth
def index():
    # Pass jellyfin_url into the HTML so the JS knows where to load images from
    return render_template_string(HTML_PAGE, default_label=DEFAULT_LABEL, jellyfin_url=JELLYFIN_URL)

@app.route('/api/known_labels')
@requires_auth
def get_known_labels():
    labels = set()
    if os.path.exists(DATA_DIR):
        for filename in os.listdir(DATA_DIR):
            if filename.endswith("_mapped_shows.json"):
                label = filename.replace("_mapped_shows.json", "")
                if label and label != "default":
                    labels.add(label)
                    
    labels.add(DEFAULT_LABEL)
    return jsonify(sorted(list(labels)))

@app.route('/api/create_label', methods=['POST'])
@requires_auth
def create_label():
    label = request.json.get('label')
    if not label: return jsonify({"error": "Missing label"}), 400
    
    db_file = get_db_file(label)
    if not os.path.exists(db_file):
        with open(db_file, 'w') as f:
            json.dump([], f)
            
    return jsonify({"success": True})

@app.route('/api/plex_shows')
@requires_auth
def get_plex_shows():
    label = request.args.get('label')
    if not label: return jsonify({"error": "No label provided"}), 400

    try:
        mapped_shows = load_mapped_shows(label)
        mapped_plex_ids = [str(m['plex_id']) for m in mapped_shows]

        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        library = plex.library.section(PLEX_LIBRARY_NAME)
        
        matching_shows = library.search(label=label)
        shows = [s for s in matching_shows if str(s.ratingKey) not in mapped_plex_ids]
        
        result = [{"id": str(s.ratingKey), "title": s.title, "year": s.year} for s in shows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search_jellyfin')
@requires_auth
def search_jellyfin():
    query = request.args.get('q', '')
    url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items"
    params = {
        "searchTerm": query,
        "IncludeItemTypes": "Series,Movie,BoxSet",
        "Recursive": "true",
        "Fields": "ProductionYear"
    }
    try:
        res = requests.get(url, headers=get_jf_headers(), params=params)
        if res.status_code != 200: return jsonify({"error": f"Status {res.status_code}"}), 500
        items = res.json().get('Items', [])
        result = []
        for item in items:
            image_url = f"{JELLYFIN_URL}/Items/{item['Id']}/Images/Primary?fillHeight=150&fillWidth=100&quality=80"
            result.append({
                "id": item['Id'], "name": item.get('Name', ''),
                "type": item.get('Type', 'Unknown'), "year": item.get('ProductionYear', ''),
                "image_url": image_url
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/apply_tag', methods=['POST'])
@requires_auth
def apply_tag():
    data = request.json
    jellyfin_id = data.get('jellyfin_id')
    plex_id = data.get('plex_id')
    title = data.get('title', 'Unknown Title') 
    label = data.get('label')
    
    if not jellyfin_id or not plex_id or not label:
        return jsonify({"error": "Missing required data"}), 400

    detail_url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items/{jellyfin_id}"
    headers = get_jf_headers()
    
    try:
        detail_res = requests.get(detail_url, headers=headers)
        if detail_res.status_code != 200: return jsonify({"error": "Failed to fetch item."}), 500
            
        item_data = detail_res.json()
        current_tags = item_data.get('Tags', [])

        if label not in current_tags:
            current_tags.append(label)
            item_data['Tags'] = current_tags
            
            update_res = requests.post(f"{JELLYFIN_URL}/Items/{jellyfin_id}", headers=headers, json=item_data)
            if update_res.status_code in [200, 204]:
                save_mapped_show(plex_id, jellyfin_id, title, label)
                return jsonify({"success": True})
            else:
                return jsonify({"error": f"Rejected (Status {update_res.status_code})"}), 500
        else:
            save_mapped_show(plex_id, jellyfin_id, title, label)
            return jsonify({"success": True, "message": "Already tagged"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/saved_matches')
@requires_auth
def saved_matches():
    label = request.args.get('label')
    if not label: return jsonify([])
    return jsonify(load_mapped_shows(label))

@app.route('/api/reapply_batch', methods=['POST'])
@requires_auth
def reapply_batch():
    data = request.json
    jellyfin_ids = data.get('jellyfin_ids', [])
    label = data.get('label')
    if not label: return jsonify({"error": "Missing label"}), 400
    
    headers = get_jf_headers()
    success_count = 0
    
    for j_id in jellyfin_ids:
        try:
            detail_url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items/{j_id}"
            detail_res = requests.get(detail_url, headers=headers)
            
            if detail_res.status_code == 200:
                item_data = detail_res.json()
                current_tags = item_data.get('Tags', [])
                
                if label not in current_tags:
                    current_tags.append(label)
                    item_data['Tags'] = current_tags
                    update_res = requests.post(f"{JELLYFIN_URL}/Items/{j_id}", headers=headers, json=item_data)
                    if update_res.status_code in [200, 204]:
                        success_count += 1
                else:
                    success_count += 1
        except Exception as e:
            continue

    return jsonify({"success": True, "count": success_count})

# NEW ROUTE: Database Health Cleanup
@app.route('/api/cleanup_database', methods=['POST'])
@requires_auth
def cleanup_database():
    label = request.json.get('label')
    if not label: return jsonify({"error": "Missing label"}), 400
    
    mapped_shows = load_mapped_shows(label)
    valid_shows = []
    removed_count = 0
    headers = get_jf_headers()
    
    for item in mapped_shows:
        j_id = item.get('jellyfin_id')
        if not j_id: continue
        
        # Check if the item actually exists in Jellyfin
        detail_url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items/{j_id}"
        res = requests.get(detail_url, headers=headers)
        
        if res.status_code == 404:
            removed_count += 1 # It's dead, let it go
        else:
            valid_shows.append(item) # It's still alive, keep it
            
    # If we found dead links, overwrite the JSON file with the clean list
    if removed_count > 0:
        with open(get_db_file(label), 'w') as f:
            json.dump(valid_shows, f, indent=4)
            
    return jsonify({"success": True, "removed": removed_count})

@app.route('/api/delete_match', methods=['POST'])
@requires_auth
def delete_match():
    data = request.json
    jellyfin_id = data.get('jellyfin_id')
    plex_id = data.get('plex_id')
    label = data.get('label')

    if not jellyfin_id or not plex_id or not label:
        return jsonify({"error": "Missing required data"}), 400

    headers = get_jf_headers()

    try:
        detail_url = f"{JELLYFIN_URL}/Users/{JELLYFIN_USER_ID}/Items/{jellyfin_id}"
        detail_res = requests.get(detail_url, headers=headers)
        
        if detail_res.status_code == 200:
            item_data = detail_res.json()
            current_tags = item_data.get('Tags', [])
            
            if label in current_tags:
                current_tags.remove(label)
                item_data['Tags'] = current_tags
                
                update_res = requests.post(f"{JELLYFIN_URL}/Items/{jellyfin_id}", headers=headers, json=item_data)
                if update_res.status_code not in [200, 204]:
                    return jsonify({"error": f"Failed to untag in Jellyfin (Status {update_res.status_code})"}), 500

        remove_mapped_show(plex_id, label)
        return jsonify({"success": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Start the Auto-Pilot background thread right before the server starts
    bg_thread = threading.Thread(target=auto_pilot_sync, daemon=True)
    bg_thread.start()
    
    app.run(host='0.0.0.0', debug=True, port=5000)
