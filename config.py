import os
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

                                                                        
BOT_TOKEN = os.getenv('BOT_TOKEN', '')

                                      
_admin_id_raw = os.getenv('ADMIN_ID', '').strip()
ADMIN_ID = int(_admin_id_raw) if _admin_id_raw.isdigit() else 0

                                 
SOUNDCLOUD_CLIENT_ID = os.getenv('SOUNDCLOUD_CLIENT_ID', '').strip()
JAMENDO_CLIENT_ID = os.getenv('JAMENDO_CLIENT_ID', '').strip()

_db_backup_chat_id_raw = os.getenv('DB_BACKUP_CHAT_ID', '').strip()
try:
    DB_BACKUP_CHAT_ID = int(_db_backup_chat_id_raw) if _db_backup_chat_id_raw else 0
except Exception:
    DB_BACKUP_CHAT_ID = 0

                   
INITIAL_USD = 500                                      
MINING_INTERVAL = 60                                          
BASE_HASHRATE = 0                   
BITCOIN_EXCHANGE_RATE = 40000