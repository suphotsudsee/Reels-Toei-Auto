# AI Reels Factory

ระบบผลิตวิดีโอ Reels อัตโนมัติบน Ubuntu + Docker:

`Research → Script → B-roll → Voice → Caption → Render → QC → Archive`

## Architecture

```mermaid
flowchart TD
    S[Celery Beat<br/>Mon/Wed/Fri 09:00] --> A[FastAPI / Pipeline]
    A --> Q[Redis Queue]
    Q --> W[Celery Worker + FFmpeg]
    W --> P[(PostgreSQL)]
    W --> M[(MinIO Archive)]
    W --> X[AI / Media Providers]
```

รายละเอียดอยู่ที่ [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Quick start

```bash
cp .env.example .env
# แก้รหัสผ่านและ API keys ใน .env
docker compose config
docker compose up -d --build
docker compose ps
curl -fsS http://localhost:8080/health
```

> ระบบต้องมี `OPENAI_API_KEY` เพื่อสร้างเสียงพากย์ หากไม่มี key งานจะหยุดพร้อมข้อความผิดพลาดแทนการสร้างคลิปเสียงเงียบ งานเผยแพร่จริงควรตรวจเนื้อหาโดยมนุษย์ก่อน post

`target_seconds` เป็นเวลาเป้าหมาย ไม่ใช่คำสั่งตัดเสียงแข็ง ระบบจะยึดความยาวเสียงจริงและเผื่อภาพท้ายคลิป 0.8 วินาทีเพื่อให้ประโยคจบสมบูรณ์ Caption ภาษาไทยจะถูกแบ่งเป็นวลีสั้นไม่เกิน 2 บรรทัดและวางใน safe area

Dashboard/API docs: `http://VPS-IP:8080/docs`  
MinIO Console: `http://VPS-IP:9001`

สร้างคลิปด้วยตนเอง:

```bash
curl -X POST http://localhost:8080/jobs \
  -H 'Content-Type: application/json' \
  -d '{"topic":"AI ในโรงพยาบาล","language":"th","target_seconds":45}'
```

ดูสถานะ:

```bash
curl http://localhost:8080/jobs/JOB_ID
```

## Production checklist

- เปลี่ยน password/secret ทุกค่าใน `.env`
- ใส่ `OPENAI_API_KEY`; ใส่ `PEXELS_API_KEY` หากต้องการ stock B-roll
- ปรับ `OPENAI_TTS_SPEED` ได้ โดยค่าเริ่มต้นภาษาไทยคือ `0.94`
- เปิด port 8080/9001 เฉพาะ IP ผู้ดูแล หรือวางหลัง HTTPS reverse proxy
- สำรอง Docker volumes: `postgres_data`, `minio_data`
- รัน `bash scripts/smoke-test.sh` หลัง deploy
