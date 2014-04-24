# ProShop Holding Tank Email Utility

Add your target directory and email address to `app.py` and call it with your client id and client secret (in that order)

Example:
    python app.py fake-account.apps.googleusercontent.com faKEseCretKeY

The first time you run it you will be given a URL you must follow, then sign in as your desired recipient email address and then copy-paste the key it gives you into the app, the app will then store a refresh token for subsequent requests.