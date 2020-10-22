# [Ref] gist.github.com/touilleMan/eb02ea40b93e52604938
import os
import posixpath
import http.server
import urllib.request, urllib.parse, urllib.error
import html
import shutil
import mimetypes
import re
from io import BytesIO

import string
import random
import threading

# [Ref] stackoverflow.com/a/2257449/4824627
def getID(size=16, chars=string.ascii_letters + string.digits):
   return ''.join(random.choice(chars) for _ in range(size))

class SimpleHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
    """Serve a GET request."""
    f = self.send_head()
    if f:
      self.copyfile(f, self.wfile)
      f.close()

  def do_HEAD(self):
    """Serve a HEAD request."""
    f = self.send_head()
    if f:
      f.close()

  def do_POST(self):
    """Serve a POST request."""
    r, info = self.deal_post_data()
    print((r, info, "by: ", self.client_address))
    f = BytesIO()
    f.write(b"<!DOCTYPE html>")
    f.write(b"<html>\n<title>Upload Result Page</title>\n")
    f.write(b"<body>\n<h2>Upload Result Page</h2>\n")
    f.write(b"<hr>\n")
    if r:
      f.write(b"<strong>Success:</strong>")
    else:
      f.write(b"<strong>Failed:</strong>")
    f.write(info.encode())
    f.write(("<br><a href=\"%s\">back</a>" % self.headers['referer']).encode())
    f.write(("<br><a href=\"/files\">all files</a>").encode())
    length = f.tell()
    f.seek(0)
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.send_header("Content-Length", str(length))
    self.end_headers()
    if f:
      self.copyfile(f, self.wfile)
      f.close()

  def deal_post_data(self):
    content_type = self.headers['content-type']
    if not content_type:
      return (False, "Content-Type header doesn't contain boundary")
    boundary = content_type.split("=")[1].encode()
    remainbytes = int(self.headers['content-length'])
    # Boundary
    line = self.rfile.readline()
    remainbytes -= len(line)
    if not boundary in line:
      return (False, "Content doesn't begin with boundary")

    # First Content-Disposition
    line = self.rfile.readline()
    remainbytes -= len(line)

    # \r\n?
    line = self.rfile.readline()
    remainbytes -= len(line)

    # Contents from `file-link`
    file_link = self.rfile.readline()
    remainbytes -= len(file_link)
    file_link = file_link.decode("utf8").strip()

    # Boundary
    line = self.rfile.readline()
    remainbytes -= len(line)
    if not boundary in line:
      return (False, "Content doesn't begin with boundary")

    # Second Content-Disposition
    line = self.rfile.readline()
    remainbytes -= len(line)
    if not "Content-Disposition".encode() in line:
      return (False, "Couldn't find Content-Disposition")

    fn = re.findall(r'Content-Disposition.*name="file"; filename="(.*)"', line.decode())
    if not fn or len(fn) < 1:
      return (False, "Can't find out file name...")

    # If there's no file name = no file uploaded...
    fn = fn[0]
    if not len(fn):
      # Then try to download the link
      if len(file_link):
        requestDownload(file_link)
        return (True, f"Link received ({file_link})")
      # If there's no link, sad face :(
      else:
        return (False, "Nothing received!")

    # Otherwise, if there is a file name, save its contents to a file
    try:
      out = open(f"./files/{getID()}-{fn}", "wb")
    except IOError:
      return (False, "Can't create file to write, do you have permission to write?")

    # Content-Type
    line = self.rfile.readline()
    remainbytes -= len(line)
    # \r\n
    line = self.rfile.readline()
    remainbytes -= len(line)

    # File content
    preline = self.rfile.readline()
    remainbytes -= len(preline)
    while remainbytes > 0:
      line = self.rfile.readline()
      remainbytes -= len(line)
      if boundary in line:
        preline = preline[0:-1]
        if preline.endswith(b'\r'):
          preline = preline[0:-1]
        out.write(preline)
        out.close()
        return (True, "File upload success!")
      else:
        out.write(preline)
        preline = line
    return (False, "Unexpected end of data")

  def send_head(self):
    """Common code for GET and HEAD commands.
    This sends the response code and MIME headers.
    Return value is either a file object (which has to be copied
    to the outputfile by the caller unless the command was HEAD,
    and must be closed by the caller under all circumstances), or
    None, in which case the caller has nothing further to do.
    """
    path = self.translate_path(self.path)
    f = None
    if os.path.isdir(path):
      if not self.path.endswith('/'):
        # redirect browser - doing basically what apache does
        self.send_response(301)
        self.send_header("Location", self.path + "/")
        self.end_headers()
        return None
      for index in "index.html", "index.htm":
        index = os.path.join(path, index)
        if os.path.exists(index):
          path = index
          break
      else:
        return self.list_directory(path)
    ctype = self.guess_type(path)
    try:
      # Always read in binary mode. Opening files in text mode may cause
      # newline translations, making the actual size of the content
      # transmitted *less* than the content-length!
      f = open(path, 'rb')
    except IOError:
      self.send_error(404, "File not found")
      return None
    self.send_response(200)
    self.send_header("Content-type", ctype)
    fs = os.fstat(f.fileno())
    self.send_header("Content-Length", str(fs[6]))
    self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
    self.end_headers()
    return f
 
  def list_directory(self, path):
    """Helper to produce a directory listing (absent index.html).
    Return value is either a file object, or None (indicating an
    error).  In either case, the headers are sent, making the
    interface the same as for send_head().
    """
    try:
      list = os.listdir(path)
    except os.error:
      self.send_error(404, "No permission to list directory")
      return None
    list.sort(key=lambda a: a.lower())
    f = BytesIO()
    displaypath = html.escape(urllib.parse.unquote(self.path))
    f.write(b'<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
    f.write(("<html>\n<title>Directory listing for %s</title>\n" % displaypath).encode())
    f.write(("<body>\n<h2>Directory listing for %s</h2>\n" % displaypath).encode())
    f.write(b"<hr>\n<ul>\n")
    for name in list:
      fullname = os.path.join(path, name)
      displayname = linkname = name
      # Append / for directories or @ for symbolic links
      if os.path.isdir(fullname):
        displayname = name + "/"
        linkname = name + "/"
      if os.path.islink(fullname):
        displayname = name + "@"
        # Note: a link to a directory displays with @ and links with /
      f.write(('<li><a href="%s">%s</a>\n'
          % (urllib.parse.quote(linkname), html.escape(displayname))).encode())
    f.write(b"</ul>\n<hr>\n</body>\n</html>\n")
    length = f.tell()
    f.seek(0)
    self.send_response(200)
    self.send_header("Content-type", "text/html")
    self.send_header("Content-Length", str(length))
    self.end_headers()
    return f

  def translate_path(self, path):
    """Translate a /-separated PATH to the local filename syntax.
    Components that mean special things to the local file system
    (e.g. drive or directory names) are ignored.  (XXX They should
    probably be diagnosed.)
    """
    # abandon query parameters
    path = path.split('?',1)[0]
    path = path.split('#',1)[0]
    path = posixpath.normpath(urllib.parse.unquote(path))
    words = path.split('/')
    words = [_f for _f in words if _f]
    path = os.getcwd()
    for word in words:
      drive, word = os.path.splitdrive(word)
      head, word = os.path.split(word)
      if word in (os.curdir, os.pardir): continue
      path = os.path.join(path, word)
    return path

  def copyfile(self, source, outputfile):
    """Copy all data between two file objects.
    The SOURCE argument is a file object open for reading
    (or anything with a read() method) and the DESTINATION
    argument is a file object open for writing (or
    anything with a write() method).
    The only reason for overriding this would be to change
    the block size or perhaps to replace newlines by CRLF
    -- note however that this the default server uses this
    to copy binary data as well.
    """
    shutil.copyfileobj(source, outputfile)

  def guess_type(self, path):
    """Guess the type of a file.
    Argument is a PATH (a filename).
    Return value is a string of the form type/subtype,
    usable for a MIME Content-type header.
    The default implementation looks the file's extension
    up in the table self.extensions_map, using application/octet-stream
    as a default; however it would be permissible (if
    slow) to look inside the data to make a better guess.
    """
    base, ext = posixpath.splitext(path)
    if ext in self.extensions_map:
      return self.extensions_map[ext]
    ext = ext.lower()
    if ext in self.extensions_map:
      return self.extensions_map[ext]
    else:
      return self.extensions_map[""]

  if not mimetypes.inited:
    mimetypes.init() # try to read system mime.types
  extensions_map = mimetypes.types_map.copy()
  extensions_map.update({
    "": "application/octet-stream", # Default
    ".gbff": "text/plain",
    ".py": "text/plain",
    ".c": "text/plain",
    ".h": "text/plain",
  })

def checkURL(url):
  if url.startswith("https://pastebin.com/raw/"):
    return (True, "")
  return (False, "Please only use 'https://pastebin.com/raw/...' links!")

# [Ref] stackoverflow.com/a/22682/4824627
def download(url):
  with urllib.request.urlopen(url) as f:
    html = f.read().decode("utf-8")
  outputfilename = f"{getID()}.gbff"
  with open(f"./files/{outputfilename}", "w", encoding="utf8") as outputfilestream:
    outputfilestream.write(html)
  print(f"Saved file '{outputfilename}' with contents from '{url}'")

def requestDownload(url):
  urlstatus, info = checkURL(url)
  if not urlstatus:
    print(info)
    return
  print(f"Requesting download of '{url}'")
  dl = threading.Thread(target=download, args=[url])
  dl.start()

def run(HandlerClass = SimpleHTTPRequestHandler,
     ServerClass = http.server.HTTPServer):
  http.server.test(HandlerClass, ServerClass)

if __name__ == "__main__":
  # Create output directory if it doesn't exist
  os.makedirs("./files", exist_ok=True)
  run()