import asyncio
import logging
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import asyncpg
import os

from core.config import get_settings

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("recurrent_events_generator")

BKK_ZONE = ZoneInfo("Asia/Bangkok")

async def generate_recurring_events():
    logger.info("🚀 Starting Recurrent Events Generator...")
    settings = get_settings()
    
    # Calculate "tomorrow" in Bangkok time
    now_bkk = datetime.now(BKK_ZONE)
    tomorrow_bkk = (now_bkk + timedelta(days=1)).date()
    # 0 = Monday, 6 = Sunday
    tomorrow_weekday = tomorrow_bkk.weekday()
    
    logger.info(f"📅 Target Date (Tomorrow): {tomorrow_bkk} (Weekday: {tomorrow_weekday})")

    settings = get_settings()
    
    # ── Assemble PostgreSQL DSN manually from config ──────────────
    import urllib.parse
    pwd_escaped = urllib.parse.quote_plus(settings.DB_PASSWORD)
    pg_dsn = f"postgres://{settings.DB_USER}:{pwd_escaped}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    conn = await asyncpg.connect(pg_dsn)
    
    try:
        # Step 1: Find all master recurrent events
        query_masters = """
            SELECT * FROM events 
            WHERE recurrence_type IN ('daily', 'weekly')
        """
        masters = await conn.fetch(query_masters)
        logger.info(f"🔍 Found {len(masters)} total recurrent master events in DB.")
        
        spawn_count = 0
        skip_count = 0
        duplicate_count = 0

        for m in masters:
            m_id = m['id']
            rtype = m['recurrence_type']
            m_date = m['event_date']
            
            # Decide if we should spawn for tomorrow
            should_spawn = False
            if rtype == 'daily':
                should_spawn = True
            elif rtype == 'weekly':
                # If the master event was on a Friday, it only spawns if tomorrow_bkk is Friday.
                if m_date and m_date.weekday() == tomorrow_weekday:
                    should_spawn = True
            
            if not should_spawn:
                skip_count += 1
                continue
                
            # Step 2: Check for duplicates for tomorrow
            # We match on title string (JSONB string match) and location or venue_id
            # to avoid spawning if the bot already parsed the announce from telegram.
            
            # Simple hash check on Russian title (since title is JSONB like {"ru": "...", "en": "..."})
            title_json = m['title']
            if isinstance(title_json, str):
                try:
                    title_dict = json.loads(title_json)
                    title_ru = title_dict.get('ru', '')
                except:
                    title_ru = title_json
            elif isinstance(title_json, dict):
                title_ru = title_json.get('ru', '')
            else:
                title_ru = ''
                
            title_ru_search = f"%\"ru\": \"{title_ru}\"%" if title_ru else "%"

            # Check if a duplicate exists for tomorrow
            query_dup = """
                SELECT id FROM events
                WHERE event_date = $1 
                  AND (title::text LIKE $2 OR title = $3)
                  AND (
                      (location_name IS NOT NULL AND location_name = $4) 
                      OR (venue_id IS NOT NULL AND venue_id = $5)
                      OR (location_name IS NULL AND venue_id IS NULL)
                  )
                LIMIT 1
            """
            
            dup = await conn.fetchrow(
                query_dup, 
                tomorrow_bkk, 
                title_ru_search, 
                m['title'], 
                m['location_name'], 
                m['venue_id']
            )
            
            if dup:
                logger.info(f"⚠️ Skipping ID {m_id} ('{title_ru}'). Duplicate already exists on {tomorrow_bkk} (Dup ID: {dup['id']}).")
                duplicate_count += 1
                continue
                
            # Step 3: Insert exact clone for tomorrow
            # Exclude id, detected_at, fingerprint (we'll generate a random md5/uuid for fingerprint if needed, but it's optional).
            # We will explicitly set event_date = tomorrow_bkk, parent_id = m_id, source = 'recurrent_job'
            
            insert_query = """
                INSERT INTO events (
                    title, category, event_date, event_time, location_name, venue_id, 
                    price_thb, summary, description, source_chat_id, source_chat_title, 
                    message_id, sender, filter_score, original_text, source, 
                    image_path, sender_id, google_maps_url, recurrence_type, parent_id
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, 
                    $7, $8, $9, $10, $11, 
                    $12, $13, $14, $15, 'recurrent_job', 
                    $16, $17, $18, $19, $20
                ) RETURNING id;
            """
            
            try:
                new_id = await conn.fetchval(
                    insert_query,
                    m['title'], m['category'], tomorrow_bkk, m['event_time'], m['location_name'], m['venue_id'],
                    m['price_thb'], m['summary'], m['description'], m['source_chat_id'], m['source_chat_title'],
                    m['message_id'], m['sender'], m['filter_score'], m['original_text'], 
                    m['image_path'], m['sender_id'], m['google_maps_url'], m['recurrence_type'], m_id
                )
                logger.info(f"✅ Spawned '{title_ru}' (Master ID: {m_id}) -> New ID: {new_id} for {tomorrow_bkk}.")
                spawn_count += 1
            except Exception as insert_err:
                logger.error(f"❌ Failed to insert clone for Master ID {m_id}: {insert_err}")
                
    except Exception as e:
        logger.error(f"🔥 Critical error running recurrent generator: {e}")
    finally:
        await conn.close()
        
    logger.info(f"🏁 Finished. Spawns: {spawn_count} | Duplicates Avoided: {duplicate_count} | Skipped (Wrong Day/Freq): {skip_count}")

if __name__ == "__main__":
    asyncio.run(generate_recurring_events())
