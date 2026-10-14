import importlib.util
import json
import tempfile
import threading
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("network_arena",root/"server.py")
server=importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class NetworkTests(unittest.TestCase):
    def test_two_clients_share_authoritative_world_over_http(self):
        (root/"data"/"tests").mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root/"data"/"tests") as temp:
            arena=server.Arena(Path(temp)/"accounts.json",seed=20)
            class Handler(server.Handler): pass
            Handler.arena=arena
            http=server.ThreadingHTTPServer(("127.0.0.1",0),Handler)
            service=threading.Thread(target=http.serve_forever,daemon=True)
            simulation=threading.Thread(target=arena.run,daemon=True)
            service.start();simulation.start()
            def request(route,body=None,token=""):
                conn=HTTPConnection("127.0.0.1",http.server_port,timeout=3)
                conn.request("POST",route,json.dumps(body or {}),{"Content-Type":"application/json","Authorization":"Bearer "+token})
                response=conn.getresponse();value=json.loads(response.read());conn.close()
                self.assertEqual(response.status,200,value)
                return value
            try:
                for route in ("/auth/guest","/arena/join","/arena/world"):
                    conn=HTTPConnection("127.0.0.1",http.server_port,timeout=3)
                    conn.request("POST",route,"{}",{"Content-Type":"application/json"})
                    response=conn.getresponse();value=json.loads(response.read());conn.close()
                    self.assertEqual(response.status,400,value)
                a=request("/auth/register",dict(username="NetworkA",email="networka@example.com",password="test-passphrase"))["token"]
                b=request("/auth/register",dict(username="NetworkB",email="networkb@example.com",password="test-passphrase"))["token"]
                aid=request("/arena/join",token=a)["player"]
                bid=request("/arena/join",token=b)["player"]
                snapshot=request("/arena/state",token=b)
                self.assertEqual(snapshot["humans"],2)
                self.assertEqual(snapshot["bots"],8)
                self.assertEqual(snapshot["player"],bid)
                old=next(f for f in snapshot["fighters"] if f["id"]==aid)
                request("/arena/state",dict(move=[1,0],yaw=0),a)
                time.sleep(.2)
                new=request("/arena/state",token=b)
                moved=next(f for f in new["fighters"] if f["id"]==aid)
                self.assertGreater(moved["x"],old["x"]+.1)
                self.assertLess(moved["x"],old["x"]+2)
                request("/arena/leave",token=a)
                remaining=request("/arena/state",token=b)
                self.assertEqual(remaining["humans"],1)
                self.assertEqual(remaining["bots"],9)
            finally:
                arena.running=False;http.shutdown();http.server_close();service.join();simulation.join()


if __name__=="__main__":unittest.main()
