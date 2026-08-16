# Architecture v1

## Components

| Component | หน้าที่ |
|---|---|
| `api` | รับงาน, ดูสถานะ, retry และ health check |
| `worker` | ทำ pipeline ทีละ stage และ render ด้วย FFmpeg |
| `beat` | สร้างงาน 3 ครั้ง/สัปดาห์ |
| PostgreSQL | metadata, stage state, error และ artifact manifest |
| Redis | Celery broker/result backend |
| MinIO | เก็บ research, script, audio, caption, final video และ QC report |

## Stage contract

ทุก stage รับ `job_id`, อ่านผล stage ก่อนหน้า, เขียน artifact ลง working directory และบันทึก state ลงฐานข้อมูล ถ้าเกิดข้อผิดพลาดงานจะเป็น `failed` พร้อม `failed_stage` และข้อความ error ทำให้ retry ได้โดยไม่สูญเสีย audit trail

1. **Research** — สร้าง facts/angles/source notes จาก topic
2. **Script** — JSON script: hook, scenes, narration, CTA
3. **B-roll** — ดาวน์โหลด Pexels ตาม scene query หรือสร้าง fallback clips
4. **Voice** — OpenAI TTS; fallback เป็น silent audio สำหรับ smoke test
5. **Caption** — สร้าง SRT จาก narration และ timing
6. **Render** — normalize/concat clips, mix voice, burn captions, 1080×1920 H.264
7. **QC** — ffprobe ตรวจ video/audio/duration/resolution และ artifact completeness
8. **Archive** — upload ทั้ง job folder เข้า MinIO และเขียน manifest

## Scheduling

Celery Beat ใช้ timezone `Asia/Bangkok` และสร้างงานวันจันทร์ พุธ ศุกร์ 09:00 น. Topic ตั้งจาก `DEFAULT_TOPIC`; เปลี่ยน schedule ได้ใน `app/celery_app.py`

## Security boundary

- Secrets มาจาก `.env` เท่านั้นและไม่ถูก bake เข้า image
- API ควรวางหลัง reverse proxy พร้อม TLS และ authentication ก่อนเปิด public
- MinIO console ไม่ควรเปิดสู่ Internet โดยตรง
- Provider downloads มี timeout และจำกัดจำนวน/ขนาดตาม pipeline

