#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import imaplib
import time
import uuid
import email
import string
from bs4 import BeautifulSoup
from email.parser import HeaderParser
from email.header import decode_header
from email.utils import parsedate,parseaddr
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

APP_NAME = 'imap2atom'
APP_LINK = 'https://bitbucket.org/florent_k/imap2atom'
APP_VERSION = '0.3'
PORT_NUMBER = 14380
MAX_NB_MAIL = 100

SERVEUR = ''
USERNAME = ''
PASSWORD = ''
FOLDER = ''
LINK = 'http://'

parser = HeaderParser()

def decode_subject(s):
  (subject,encode) = decode_header(s)[0]
  if(encode=='utf-8' or encode==None):
    sub = str(subject)
  else :
    sub = subject.decode(encode).encode('utf-8')
  return sub.replace("&","&amp;")

def decode_date(s):
  d = parsedate(s)
  if d == None :
    return datetime.utcnow()
  else:
    return datetime.fromtimestamp(time.mktime(d)) 

def fetch_header(msg):
  return (decode_subject(msg['Subject']),decode_date(msg['Date']),parseaddr(msg['Message-ID'])[1],parseaddr(msg['From']))

def find_end_url(begin,text):
  for i in range(begin,len(text)):
    if text[i] == ' ' : return i
    if text[i] == '\n' : return i
    if text[i] == ')' : return i
    if text[i] == ']' : return i
  return len(text)

def find_first_url(text):
  begin = text.find("https://")
  
  if(begin == -1): begin = text.find("http://")

  if(begin > 0):
    end = find_end_url(begin,text)
    return text[begin:end]
  else:
    return "#"
    
def find_first_html_anchor(text):
    soup = BeautifulSoup(text, "lxml")

    for a in soup.find_all('a'):
      url = a.get("href")
      if(url): return url
      url = a.get("data-linkto")
      if(url): return url
    
    return "#"    

def fetch_first_url(msg):

  if msg.is_multipart():
    for part in msg.get_payload():
      if(part.get_content_type() == 'text/html'):
        return fetch_first_url(part)
  else:
    content_type = msg.get_content_type()
    payload = msg.get_payload(decode=True).strip()

    if content_type == 'text/plain':
        return find_first_url(payload)
    if content_type == 'text/html':
        return find_first_html_anchor(payload)
  return "#"

def fetch_first_url_clean(msg):
  return fetch_first_url(msg).replace("&","&amp;")

def fetch_mail(m):
  msg = email.message_from_bytes(m[1])
  return (fetch_first_url_clean(msg),fetch_header(msg))

def fetch_mails(nb) :
  mail = imaplib.IMAP4_SSL(SERVEUR)
  mail.login(USERNAME, PASSWORD)
  mail.list()
  # Out: list of "folders" aka labels in gmail.
  mail.select(FOLDER) # connect to inbox.

  result, data = mail.uid('search', None, "ALL")
   
  uid_list = b",".join(data[0].split()[-nb:])

  result, data = mail.uid('fetch', uid_list, '(RFC822)')

  return [fetch_mail(email) for email in reversed(data) if len(email) > 1]    


def generate_entry(link,title,date,uid,name,addr):
  if (link == "#"):
    domain = addr.split("@")[1]
    link = "http://"+domain.split(".")[-2]+"."+domain.split(".")[-1]

  e=['\n<entry>',
    '\t<title>[' + name  + '] ' +  title + '</title>',
#    '\t<link href="<![CDATA[' + link + ']]>"/>',
    '\t<link href="' + link + '"/>',
    '\t<id>' + uid + '</id>',
    '\t<updated>' + date.isoformat("T") + "Z" + '</updated>',
    '\t<author>',
      '\t\t<name>' + name + '</name>',
      '\t\t<email>' + addr + '</email>',
    '\t</author>',
    '</entry>']
  return '\n'.join(e)

def generate_atom(headers):
  id_prefix = 'tag:imap2rss' + USERNAME + '@' + SERVEUR + '/' + FOLDER
  atom_pref=['<?xml version="1.0" encoding="utf-8"?>','<feed xmlns="http://www.w3.org/2005/Atom">']
  atom_header = [
    '<title>' + USERNAME + ' Inbox </title>',
    '<link href="' + LINK + '"/>',
    '<updated>' + datetime.utcnow().isoformat("T")  + "Z" + '</updated>',
    '<generator uri="' + APP_LINK + '" version="' + APP_VERSION + '">',
    '\t' + APP_NAME,
    '</generator>',
    '<id>' + id_prefix + '</id>']
  atom_entry = [generate_entry(l,h[0],h[1],id_prefix + "/" + h[2], decode_subject(h[3][0]), h[3][1]) for (l,h) in headers if h[0] != None]
  atom_suffix = ['</feed>']

  return '\n'.join(atom_pref + atom_header + atom_entry + atom_suffix)


class MyHandler(BaseHTTPRequestHandler):
    def do_GET(s):
      params = parse_qs(urlparse(s.path).query)

      if ("nb" in params.keys()) and (len(params["nb"])>0):
        nb = int(params["nb"][0])
      else :
        nb = 10

      nb = min(nb,MAX_NB_MAIL)

      s.send_response(200)
      s.send_header("Content-type", "application/atom+xml")
      s.end_headers()
      s.wfile.write(generate_atom(fetch_mails(nb)).encode())

def main():
    try:
        server = HTTPServer(('', PORT_NUMBER), MyHandler)
        print ('Started pymap2atom...')
        server.serve_forever()
    except KeyboardInterrupt:
        print ('^C received, shutting down server')
        server.socket.close()


def test():
  print (generate_atom(fetch_mails(10)))
  #print fetch_mails(10)

if __name__ == "__main__":
  main()

