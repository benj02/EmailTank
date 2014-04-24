import base64
import imaplib
import json
import smtplib
import sys
import urllib
import email
import os

### Config
CLIENT_ID = sys.argv[1]
CLIENT_SECRET = sys.argv[2]
TARGET_DIR = "target"
SOURCE_EMAIL = "benj@procnc.com"
### /Config


# The URL root for accessing Google Accounts.
GOOGLE_ACCOUNTS_BASE_URL = 'https://accounts.google.com'


# Hardcoded dummy redirect URI for non-web apps.
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


def AccountsUrl(command):
  """Generates the Google Accounts URL.

  Args:
    command: The command to execute.

  Returns:
    A URL for the given command.
  """
  return '%s/%s' % (GOOGLE_ACCOUNTS_BASE_URL, command)


def UrlEscape(text):
  # See OAUTH 5.1 for a definition of which characters need to be escaped.
  return urllib.quote(text, safe='~-._')


def UrlUnescape(text):
  # See OAUTH 5.1 for a definition of which characters need to be escaped.
  return urllib.unquote(text)


def FormatUrlParams(params):
  """Formats parameters into a URL query string.

  Args:
    params: A key-value map.

  Returns:
    A URL query string version of the given parameters.
  """
  param_fragments = []
  for param in sorted(params.iteritems(), key=lambda x: x[0]):
    param_fragments.append('%s=%s' % (param[0], UrlEscape(param[1])))
  return '&'.join(param_fragments)


def GeneratePermissionUrl(client_id, scope='https://mail.google.com/'):
  """Generates the URL for authorizing access.

  This uses the "OAuth2 for Installed Applications" flow described at
  https://developers.google.com/accounts/docs/OAuth2InstalledApp

  Args:
    client_id: Client ID obtained by registering your app.
    scope: scope for access token, e.g. 'https://mail.google.com'
  Returns:
    A URL that the user should visit in their browser.
  """
  params = {}
  params['client_id'] = client_id
  params['redirect_uri'] = REDIRECT_URI
  params['scope'] = scope
  params['response_type'] = 'code'
  return '%s?%s' % (AccountsUrl('o/oauth2/auth'),
                    FormatUrlParams(params))


def AuthorizeTokens(client_id, client_secret, authorization_code):
  """Obtains OAuth access token and refresh token.

  This uses the application portion of the "OAuth2 for Installed Applications"
  flow at https://developers.google.com/accounts/docs/OAuth2InstalledApp#handlingtheresponse

  Args:
    client_id: Client ID obtained by registering your app.
    client_secret: Client secret obtained by registering your app.
    authorization_code: code generated by Google Accounts after user grants
        permission.
  Returns:
    The decoded response from the Google Accounts server, as a dict. Expected
    fields include 'access_token', 'expires_in', and 'refresh_token'.
  """
  params = {}
  params['client_id'] = client_id
  params['client_secret'] = client_secret
  params['code'] = authorization_code
  params['redirect_uri'] = REDIRECT_URI
  params['grant_type'] = 'authorization_code'
  request_url = AccountsUrl('o/oauth2/token')

  response = urllib.urlopen(request_url, urllib.urlencode(params)).read()
  return json.loads(response)


def RefreshToken(client_id, client_secret, refresh_token):
  """Obtains a new token given a refresh token.

  See https://developers.google.com/accounts/docs/OAuth2InstalledApp#refresh

  Args:
    client_id: Client ID obtained by registering your app.
    client_secret: Client secret obtained by registering your app.
    refresh_token: A previously-obtained refresh token.
  Returns:
    The decoded response from the Google Accounts server, as a dict. Expected
    fields include 'access_token', 'expires_in', and 'refresh_token'.
  """
  params = {}
  params['client_id'] = client_id
  params['client_secret'] = client_secret
  params['refresh_token'] = refresh_token
  params['grant_type'] = 'refresh_token'
  request_url = AccountsUrl('o/oauth2/token')

  response = urllib.urlopen(request_url, urllib.urlencode(params)).read()
  return json.loads(response)

def GenerateOAuth2String(username, access_token, base64_encode=True):
  """Generates an IMAP OAuth2 authentication string.

  See https://developers.google.com/google-apps/gmail/oauth2_overview

  Args:
    username: the username (email address) of the account to authenticate
    access_token: An OAuth2 access token.
    base64_encode: Whether to base64-encode the output.

  Returns:
    The SASL argument for the OAuth2 mechanism.
  """
  auth_string = 'user=%s\1auth=Bearer %s\1\1' % (username, access_token)
  if base64_encode:
    auth_string = base64.b64encode(auth_string)
  return auth_string


def WalkEmails(user, auth_string):
  """
  Args:
    user: The Gmail username (full email address)
    auth_string: A valid OAuth2 string, as returned by GenerateOAuth2String.
        Must not be base64-encoded, since imaplib does its own base64-encoding.
  """
  print
  imap_conn = imaplib.IMAP4_SSL('imap.gmail.com')
  imap_conn.debug = 4
  imap_conn.authenticate('XOAUTH2', lambda x: auth_string)
  imap_conn.select('[Gmail]/All Mail')
  res, data = imap_conn.search(None, "(UNSEEN)")
  data = data[0].split()
  for datum in data:
    res_, data_ = imap_conn.fetch(datum, "(RFC822)")
    body = data_[0][1]
    mail = email.message_from_string(body)
    imap_conn.store(datum,'+FLAGS', '\\Seen')
    imap_conn.expunge()
    if mail.get_content_maintype() != "multipart": continue
    print "["+mail["From"]+"] :" + (mail["Subject"] or "[No Subject]")
    for part in mail.walk():
      if part.get_content_maintype() == 'multipart':
        continue
      if part.get('Content-Disposition') is None:
        continue

      filename = part.get_filename()
      if filename != None:
        att_path = os.path.join(TARGET_DIR, filename)

        while os.path.isfile(att_path):
          att_path += "_" + att_path # Add underscores until name is unique
        with open(att_path, 'wb') as f:
          f.write(part.get_payload(decode=True))



def GetInitialAccess():
  print 'To authorize token, visit this url and follow the directions:'
  print '  %s' % GeneratePermissionUrl(CLIENT_ID)
  authorization_code = raw_input('Enter verification code: ')
  response = AuthorizeTokens(CLIENT_ID, CLIENT_SECRET,
                              authorization_code)
  print 'Refresh Token: %s' % response['refresh_token']
  print 'Access Token: %s' % response['access_token']
  print 'Access Token Expiration Seconds: %s' % response['expires_in']
  return response["access_token"], response["refresh_token"]

def RefreshAccess(refresh_token):
  response = RefreshToken(CLIENT_ID, CLIENT_SECRET,
                          refresh_token)
  print 'Access Token: %s' % response['access_token']
  print 'Access Token Expiration Seconds: %s' % response['expires_in']
  return response['access_token']

if os.path.isfile("__refresh_token"):
  refresh_token = None
  with open("__refresh_token", "r") as f:
    refresh_token = f.read()

  access_token = RefreshAccess(refresh_token)
  WalkEmails(SOURCE_EMAIL, GenerateOAuth2String(SOURCE_EMAIL, access_token, base64_encode=False))
else:
  access_token, refresh_token = GetInitialAccess()
  with open("__refresh_token", "w") as f:
    f.write(refresh_token)
    print "Wrote refresh token: %s" % refresh_token
  WalkEmails(SOURCE_EMAIL, GenerateOAuth2String(SOURCE_EMAIL, access_token, base64_encode=False))
