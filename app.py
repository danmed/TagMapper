import requests
import json
import os
from flask import Flask, jsonify, request, render_template_string
from plexapi.server import PlexServer

# --- CONFIGURATION (Docker Ready!) ---
PLEX_URL = os.getenv('PLEX_URL', 'http://192.168.2.203:32400')
PLEX_TOKEN = os.getenv('PLEX_TOKEN', 'YOUR_PLEX_TOKEN')
PLEX_LIBRARY_NAME = os.getenv('PLEX_LIBRARY_NAME', 'TV')

JELLYFIN_URL = os.getenv('JELLYFIN_URL', 'http://192.168.2.202:8096') 
JELLYFIN_API_KEY = os.getenv('JELLYFIN_API_KEY', 'YOUR_JELLYFIN_KEY')
JELLYFIN_USER_ID = os.getenv('JELLYFIN_USER_ID', 'YOUR_ADMIN_ID') 

# We now point to the data directory, not a specific file
DATA_DIR = os.getenv('DATA_DIR', '/data')

# We can keep a default fallback label if none is typed
DEFAULT_LABEL = os.getenv('TARGET_LABEL', 'LauraTV')
# -------------------------------------

app = Flask(__name__)

# --- DATABASE FUNCTIONS (Now Dynamic by Label!) ---
def get_db_file(label):
    """Generates a safe filename based on the provided label."""
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
        .label-bar input { padding: 10px; border-radius: 4px; border: none; background: #2c2c2c; color: #fff; font-size: 16px; font-weight: bold; width: 250px;}
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
        
        .del-btn { background: #d32f2f; color: #fff; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;}
        .del-btn:hover { background: #f44336; }
        .sort-btn { background: #444; color: #fff; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;}
        .sort-btn:hover { background: #555; }
        
        .success-msg { color: #4caf50; font-weight: bold; display: none; margin-bottom: 15px; }

        .db-item { display: flex; align-items: center; gap: 15px; background: #2c2c2c; padding: 10px 15px; margin-bottom: 8px; border-radius: 6px; color: #fff; font-style: normal; }
        .db-item input[type="checkbox"] { width: 18px; height: 18px; cursor: pointer; }
        .db-toolbar { display: flex; gap: 15px; margin-bottom: 15px; align-items: center; background: #1e1e1e; padding: 15px; border-radius: 8px;}
        .db-status { color: #aaa; margin-left: auto; font-style: italic; }
    </style>
</head>
<body>

    <!-- GLOBAL LABEL BAR -->
    <div class="label-bar">
        <span><strong>Active Label:</strong></span>
        <input type="text" id="globalLabel" value="{{ default_label }}">
        <button onclick="changeLabel()">Load Label Data</button>
    </div>

    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('mapper')" id="tab-mapper">1. Match New Shows</button>
        <button class="tab-btn" onclick="switchTab('database')" id="tab-database">2. Saved Database & Re-Apply</button>
    </div>

    <!-- TAB 1: THE MAPPER -->
    <div id="mapper" class="tab-content active">
        <div class="column">
            <h2>Select Plex Show</h2>
            <p>Pending shows in Plex with label: <strong id="displayLabel">None Loaded</strong></p>
            <div class="list-container" id="plexList">Enter a label and click 'Load Label Data' to begin.</div>
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

    <!-- TAB 2: THE DATABASE -->
    <div id="database" class="tab-content" style="flex-direction: column;">
        <div class="db-toolbar">
            <button class="action-btn" onclick="selectAllDB()">Select All</button>
            <button class="action-btn" onclick="deselectAllDB()">Deselect All</button>
            <button class="tag-btn" onclick="reapplySelected()">Re-Apply Tags to Selected</button>
            <button id="sortBtn" class="sort-btn" onclick="toggleSort()">Sort: A-Z ↓</button>
            <div class="db-status" id="dbStatus"></div>
        </div>
        <div class="list-container" id="dbList" style="background: #1e1e1e; border-radius: 8px; padding: 20px;">
            Enter a label and click 'Load Label Data' to begin.
        </div>
    </div>

    <script>
        let currentPlexShow = null;
        let cachedDbData = [];
        let dbSortOrder = 'asc'; 
        let activeTab = 'mapper'; 
        let hasLoaded = false; // Prevents loading until the button is clicked!

        function getActiveLabel() {
            return document.getElementById('globalLabel').value.trim();
        }

        function changeLabel() {
            let label = getActiveLabel();
            if(!label) return alert("Label cannot be empty!");
            
            hasLoaded = true; // Unlock the app!
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
            
            // Only try to load data if they have clicked the blue button at least once
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

            sortedData.forEach(item => {
                const div = document.createElement('div');
                div.className = 'db-item';
                let displayTitle = item.title ? item.title : `Unknown Title (Plex ID: ${item.plex_id})`;
                div.innerHTML = `
                    <input type="checkbox" class="db-checkbox" value="${item.jellyfin_id}">
                    <div class="jf-info">
                        <strong>${displayTitle}</strong>
                    </div>
                    <button class="del-btn" onclick="deleteMatch('${item.plex_id}', '${item.jellyfin_id}', this)">Unlink & Remove</button>
                `;
                list.appendChild(div);
            });
            
            document.getElementById('dbStatus').innerText = `${sortedData.length} matches in database`;
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
            let label = getActiveLabel();
            
            statusDiv.innerText = `Re-applying tags to ${jellyfinIds.length} items...`;
            
            try {
                const response = await fetch('/api/reapply_batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ jellyfin_ids: jellyfinIds, label: label })
                });
                const result = await response.json();
                
                if(result.success) {
                    statusDiv.innerHTML = `<span style="color:#4caf50">✅ Successfully tagged ${result.count} items!</span>`;
                    setTimeout(() => deselectAllDB(), 1000);
                } else {
                    statusDiv.innerHTML = `<span style="color:red">❌ Error: ${result.error}</span>`;
                }
            } catch (err) {
                statusDiv.innerText = "Connection error.";
            }
        }

        // NOTE: We completely removed the loadPlexShows() auto-trigger here!
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
def index():
    return render_template_string(HTML_PAGE, default_label=DEFAULT_LABEL)

@app.route('/api/plex_shows')
def get_plex_shows():
    label = request.args.get('label')
    if not label: return jsonify({"error": "No label provided"}), 400

    try:
        mapped_shows = load_mapped_shows(label)
        mapped_plex_ids = [str(m['plex_id']) for m in mapped_shows]

        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        library = plex.library.section(PLEX_LIBRARY_NAME)
        
        shows = [s for s in library.all() if label in [l.tag for l in s.labels] and str(s.ratingKey) not in mapped_plex_ids]
        result = [{"id": str(s.ratingKey), "title": s.title, "year": s.year} for s in shows]
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search_jellyfin')
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
def saved_matches():
    label = request.args.get('label')
    if not label: return jsonify([])
    return jsonify(load_mapped_shows(label))

@app.route('/api/reapply_batch', methods=['POST'])
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
            print(f"Failed to reapply to {j_id}: {e}")
            continue

    return jsonify({"success": True, "count": success_count})

@app.route('/api/delete_match', methods=['POST'])
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
    app.run(host='0.0.0.0', debug=True, port=5000)
