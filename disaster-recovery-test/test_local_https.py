#!/usr/bin/env python3
"""Actual disposable loopback TLS/HTTP/SQLite fixture, NOT FastAPI/HAProxy recovery."""
import datetime
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import ssl
import tempfile
import threading
import time
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT=Path(__file__).resolve().parent/'evidence/real'
HOST='recovery-fixture.example.invalid'


def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();checks=[];result={'scope':'REAL LOCAL TLS/SQLITE FIXTURE ONLY — NOT PRODUCTION SOFTWARE RECOVERY',
      'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':str(uuid.uuid4())}
    def check(name,condition):
        if not condition:raise AssertionError(name)
        checks.append({'check':name,'result':'PASS'})
    with tempfile.TemporaryDirectory(prefix='https-fixture-',dir=ROOT) as tmp:
        base=Path(tmp)
        # Inventory/checkpoint is established before server startup and CRUD.
        result['inventory']={'bind':'127.0.0.1','port':'ephemeral','runtime':'Python stdlib HTTPServer',
                             'disposable_paths':['fixture.sqlite','checkpoint.sqlite','tls.key','tls.crt'],
                             'production_credentials_used':False,'public_dns_changes':False}
        dbpath=base/'fixture.sqlite'
        db=sqlite3.connect(dbpath);db.execute('CREATE TABLE item(id INTEGER PRIMARY KEY,title TEXT)')
        db.execute("INSERT INTO item VALUES(1,'checkpoint fixture')");db.commit();db.close()
        shutil.copy2(dbpath,base/'checkpoint.sqlite')
        checkpoint_hash=hashlib.sha256(dbpath.read_bytes()).hexdigest()
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,HOST)])
        now=datetime.datetime.now(datetime.timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1))
              .not_valid_after(now+datetime.timedelta(hours=1))
              .add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]),critical=False)
              .sign(key,hashes.SHA256()))
        (base/'tls.key').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (base/'tls.key').chmod(0o600)
        (base/'tls.crt').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        db=sqlite3.connect(dbpath,check_same_thread=False)
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,status,body):
                data=json.dumps(body).encode();self.send_response(status)
                self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
                self.end_headers();self.wfile.write(data)
            def dispatch(self):
                if self.headers.get('Host')!=HOST:return self.reply(421,{'error':'fixture route mismatch'})
                if self.command=='GET' and self.path=='/health':return self.reply(200,{'status':'ok','fixture':True})
                if self.headers.get('Authorization')!='Bearer fixture-only-token':return self.reply(401,{'error':'fixture unauthorized'})
                if self.command=='GET':return self.reply(200,db.execute('SELECT id,title FROM item ORDER BY id').fetchall())
                if self.command=='POST':db.execute("INSERT INTO item VALUES(2,'created over TLS')")
                elif self.command=='PUT':db.execute("UPDATE item SET title='updated over TLS' WHERE id=2")
                elif self.command=='DELETE':db.execute('DELETE FROM item WHERE id=2')
                db.commit();return self.reply(200,{'ok':True})
            do_GET=dispatch;do_POST=dispatch;do_PUT=dispatch;do_DELETE=dispatch
        server=HTTPServer(('127.0.0.1',0),Handler)
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(base/'tls.crt',base/'tls.key')
        server.socket=tls.wrap_socket(server.socket,server_side=True)
        port=server.server_address[1];result['inventory']['port']=port
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        trust=ssl.create_default_context(cafile=str(base/'tls.crt'))
        def request(method='GET',path='/health',host=HOST,sni=HOST,token=None):
            with socket.create_connection(('127.0.0.1',port),timeout=4) as raw:
                with trust.wrap_socket(raw,server_hostname=sni) as stream:
                    headers=f'{method} {path} HTTP/1.0\r\nHost: {host}\r\n'
                    if token:headers+='Authorization: Bearer '+token+'\r\n'
                    stream.sendall((headers+'Content-Length: 0\r\n\r\n').encode())
                    chunks=[]
                    while True:
                        data=stream.recv(65536)
                        if not data:break
                        chunks.append(data)
            head,body=b''.join(chunks).split(b'\r\n\r\n',1)
            return int(head.split(b'\r\n')[0].split()[1]),json.loads(body)
        try:
            thread.start()
            status,body=request();check('TLS certificate/hostname validation and health',status==200 and body['fixture'])
            check('wrong HTTP Host rejected',request(host='wrong.example.invalid')[0]==421)
            try:request(sni='wrong.example.invalid')
            except ssl.SSLCertVerificationError:check('wrong TLS hostname rejected',True)
            else:raise AssertionError('Wrong TLS identity accepted')
            check('unauthenticated request rejected',request(path='/items')[0]==401)
            check('invalid fixture credential rejected',request(path='/items',token='invalid')[0]==401)
            kwargs={'path':'/items','token':'fixture-only-token'}
            check('create via TLS fixture',request('POST',**kwargs)[0]==200)
            check('read via TLS fixture',[2,'created over TLS'] in request(**kwargs)[1])
            check('update via TLS fixture',request('PUT',**kwargs)[0]==200 and [2,'updated over TLS'] in request(**kwargs)[1])
            check('delete via TLS fixture',request('DELETE',**kwargs)[0]==200 and len(request(**kwargs)[1])==1)
            check('SQLite integrity',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5);db.close()
        check('fixture server stopped and socket closed',not thread.is_alive() and server.socket.fileno()==-1)
        # Deliberately mutate and then restore only the disposable local DB.
        db=sqlite3.connect(dbpath);db.execute("INSERT INTO item VALUES(77,'rollback mutation')");db.commit();db.close()
        shutil.copy2(base/'checkpoint.sqlite',dbpath)
        check('checkpoint rollback restores original DB bytes',hashlib.sha256(dbpath.read_bytes()).hexdigest()==checkpoint_hash)
        result['checks']=checks;result['checkpoint_sha256']=checkpoint_hash
        fixture_path=str(base)
    check('fixture directory and generated private key removed',not Path(fixture_path).exists())
    result['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    result['duration_local_seconds']=round(time.monotonic()-start,4)
    result['status']='PASS';result['checks']=checks
    (ROOT/'local-https-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'local_fixture_checks':len(checks),'status':'PASS','server_stopped':True,'fixture_removed':True,
                      'local_seconds':result['duration_local_seconds']}))


if __name__=='__main__':main()
