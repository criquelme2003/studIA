import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://dzeckogdoxxirylxjbsu.supabase.co")

SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR6ZWNrb2dkb3h4aXJ5bHhqYnN1Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDIyMzE0NCwiZXhwIjoyMDg5Nzk5MTQ0fQ.eYZHA_09Re9eiryndQoQ2AFsajm0l8eBpcByZfjWbeA")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAPoIbJffYeEMbgu4_N0wUld1IgxaHIPk4")
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"
).split(",")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY must be set")
