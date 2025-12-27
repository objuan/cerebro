
import asyncio
import sqlite3
from datetime import datetime
import time
import logging
import json
from typing import Optional, List, Dict
from uuid import uuid4

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DB_FILE = "db/crypto.db"
CONFIG_FILE = "config/cerebro.json"

class MessageDatabase:
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL;")

    def init(self):
        self.conn.execute("""
        CREATE TABLE IF NOT EXISTS ib_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            type TEXT NOT NULL,
            correlation_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME
        )
        """)
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ib_messages_receiver_status
        ON ib_messages(receiver, status)
        """)
        self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_ib_messages_correlation
        ON ib_messages(correlation_id)
        """)
        self.conn.commit()

##############################

class AsyncMessageClient:
    def __init__(self, db: MessageDatabase, name: str):
        self.db = db
        self.name = name
        self._queue = asyncio.Queue()
        self._running = False
        self.sendIds= []

    async def send_request(self, receiver: str, payload: Dict) -> str:
        cid = str(uuid4())

        self.db.conn.execute("""
            INSERT INTO ib_messages
            (sender, receiver, type, correlation_id, payload)
            VALUES (?, ?, 'request', ?, ?)
        """, (
            self.name,
            receiver,
            cid,
            json.dumps(payload)
        ))
        self.db.conn.commit()
        self.sendIds.append(cid)

        timeout = 10.0
        deadline = asyncio.get_running_loop().time() + timeout
        while not self.tick(cid):
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Timeout in attesa di cid={cid}")
            await asyncio.sleep(0.1)

    def tick(self,cid)-> bool:
 
        sql = f"""
                SELECT id,payload,correlation_id
                FROM ib_messages
                WHERE receiver = '{self.name}'
                  AND type = 'response'
                  AND correlation_id = '{cid}'
                  AND status = 'pending'
                ORDER BY created_at DESC
            """
        #logger.debug(sql)
        cur = self.db.conn.execute(sql)
        rows = cur.fetchall()
        if len(rows)>0:
            #results = []
            ids_to_update = []

            # 2️⃣ scandisci righe
            for row in rows:
                '''
                results.append({
                    "id": row["id"],
                    "correlation_id": row["correlation_id"],
                    "payload": json.loads(row["payload"])
                })
                '''
                ids_to_update.append(row["id"])
            
            # 3️⃣ UPDATE unico
            if ids_to_update:

                placeholders = ",".join("?" for _ in ids_to_update)

                sql_update = f"""
                    UPDATE ib_messages
                    SET status = 'done',
                        processed_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                """

                self.db.conn.execute(sql_update, ids_to_update)
                self.db.conn.commit()

            logger.debug("RETURN")
            return True
            #self.sendIds= []
        else:
            return False

    async def listen(self, poll_interval: float = 0.2):
        """
        Loop async che riceve risposte e le mette in coda
        """
        self._running = True

        while self._running:
            cur = self.db.conn.execute("""
                SELECT id, correlation_id, payload
                FROM ib_messages
                WHERE receiver = ?
                  AND type = 'response'
                  AND status = 'pending'
                ORDER BY created_at
            """, (self.name,))

            rows = cur.fetchall()

            for row in rows:
                payload = json.loads(row["payload"])

                if self.on_receive:
                    self.on_receive(payload)
                else:
                    await self._queue.put({
                        "correlation_id": row["correlation_id"],
                        "payload": payload
                    })

                self.db.conn.execute("""
                    UPDATE ib_messages
                    SET status = 'done',
                        processed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (row["id"],))

            if rows:
                self.db.conn.commit()

            await asyncio.sleep(poll_interval)

    async def recv(self) -> Dict:
        """
        Attende una risposta (async)
        """
        return await self._queue.get()

    def stop(self):
        self._running = False

class MessageClient:
    def __init__(self, db: MessageDatabase, name: str):
        self.db = db
        self.name = name
        self.sendMap = {}
        self.sendIds= []

    def send_request(
        self,
        receiver: str,
        payload: Dict, 
        onReceive
    ) -> str:
        correlation_id = str(uuid4())

        self.db.conn.execute("""
            INSERT INTO ib_messages
            (sender, receiver, type, correlation_id, payload)
            VALUES (?, ?, 'request', ?, ?)
        """, (
            self.name,
            receiver,
            correlation_id,
            json.dumps(payload)
        ))
        self.db.conn.commit()
        self.sendIds.append(correlation_id)
        self.sendMap[correlation_id] = (receiver,payload,onReceive)
        return correlation_id
    
    def tick(self):
        if len(self.sendIds) == 0:
            return
        _current_ids = self.sendIds.copy()
        s_ids = str(_current_ids)[1:-1]
      
        sql = f"""
                SELECT id,payload,correlation_id
                FROM ib_messages
                WHERE receiver = '{self.name}'
                  AND type = 'response'
                  AND correlation_id in ({s_ids})
                  AND status = 'pending'
                ORDER BY created_at DESC
            """
        #logger.debug(sql)
        cur = self.db.conn.execute(sql)

        rows = cur.fetchall()
        #results = []
        ids_to_update = []

        # 2️⃣ scandisci righe
        for row in rows:
            '''
            results.append({
                "id": row["id"],
                "correlation_id": row["correlation_id"],
                "payload": json.loads(row["payload"])
            })
            '''
            ids_to_update.append(row["id"])
            map = self.sendMap[row["correlation_id"]]
            #logger.debug(map)
            map[2](map[0],json.loads(row["payload"]))
            #return json.loads(row["payload"])

         # 3️⃣ UPDATE unico
        if ids_to_update:

            placeholders = ",".join("?" for _ in ids_to_update)

            sql_update = f"""
                UPDATE ib_messages
                SET status = 'done',
                    processed_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
            """

            self.db.conn.execute(sql_update, ids_to_update)
            self.db.conn.commit()
        
        for i in _current_ids:
            del self.sendMap[i]
        self.sendIds =  [x for x in self.sendIds if x not in _current_ids]
        logger.debug(f"END { self.sendIds } { self.sendMap }")
        #self.sendIds= []


    def wait_response(
        self,
        correlation_id: str,
        timeout: float = 10.0,
        poll_interval: float = 0.2
    ) -> Optional[Dict]:
        deadline = time.time() + timeout

        while time.time() < deadline:
            cur = self.db.conn.execute("""
                SELECT payload
                FROM ib_messages
                WHERE receiver = ?
                  AND type = 'response'
                  AND correlation_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (self.name, correlation_id))

            row = cur.fetchone()
            if row:
                return json.loads(row["payload"])

            time.sleep(poll_interval)

        return None
    
class MessageServer:
    def __init__(self, db: MessageDatabase, name: str):
        self.db = db
        self.name = name

    def clear(self):
        self.db.conn.execute("""
            DELETE FROM ib_messages
        """
        )
        self.db.conn.commit()
         
    def fetch_requests(self, limit: int = 10) -> List[sqlite3.Row]:
        cur = self.db.conn.execute("""
            SELECT *
            FROM ib_messages
            WHERE receiver = ?
              AND type = 'request'
              AND status = 'pending'
            ORDER BY created_at
            LIMIT ?
        """, (self.name, limit))

        return cur.fetchall()

    def send_response(
        self,
        request_row: sqlite3.Row,
        payload: Dict
    ):
        # risposta
        self.db.conn.execute("""
            INSERT INTO ib_messages
            (sender, receiver, type, correlation_id, payload)
            VALUES (?, ?, 'response', ?, ?)
        """, (
            self.name,
            request_row["sender"],
            request_row["correlation_id"],
            json.dumps(payload)
        ))

        # marca request come completata
        self.db.conn.execute("""
            UPDATE ib_messages
            SET status = 'done',
                processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (request_row["id"],))

        self.db.conn.commit()

    def send_error(
        self,
        request_row: sqlite3.Row,
        error: str
    ):
        self.db.conn.execute("""
            UPDATE ib_messages
            SET status = 'error',
                error = ?,
                processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (error, request_row["id"]))
        self.db.conn.commit()


class AsyncMessageServer:
    def __init__(self, db: MessageDatabase, name: str):
        self.db = db
        self.name = name

    async def fetch_requests(self, limit: int = 10):
        cur = await self.db.conn.execute("""
            SELECT *
            FROM ib_messages
            WHERE receiver = ?
              AND type = 'request'
              AND status = 'pending'
            ORDER BY created_at
            LIMIT ?
        """, (self.name, limit))

        return await cur.fetchall()

    async def send_response(self, request_row, payload: Dict):
        await self.db.conn.execute("""
            INSERT INTO ib_messages
            (sender, receiver, type, correlation_id, payload)
            VALUES (?, ?, 'response', ?, ?)
        """, (
            self.name,
            request_row["sender"],
            request_row["correlation_id"],
            json.dumps(payload)
        ))

        await self.db.conn.execute("""
            UPDATE ib_messages
            SET status = 'done',
                processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (request_row["id"],))

        await self.db.conn.commit()