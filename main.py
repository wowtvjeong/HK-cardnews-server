from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import re

app = FastAPI()

# 모든 도메인 허용 (내 HTML 파일이 어디서든 접근 가능)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

def extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    # URL이 아니라 ID만 넘어온 경우
    if re.match(r"^[a-zA-Z0-9_-]{11}$", url):
        return url
    raise HTTPException(status_code=400, detail="유효한 유튜브 URL이 아닙니다")

@app.get("/")
def root():
    return {"status": "ok", "message": "카드뉴스 자막 서버 정상 작동 중"}

@app.get("/transcript")
def get_transcript(url: str = Query(..., description="유튜브 URL 또는 Video ID")):
    video_id = extract_video_id(url)

    # 한국어 → 영어 → 자동생성 자막 순으로 시도
    try_langs = [
        ["ko"],
        ["en"],
        ["ko", "en"],
    ]

    transcript_text = ""
    used_lang = ""

    for langs in try_langs:
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            transcript_text = " ".join(t["text"].strip() for t in transcript if t["text"].strip())
            used_lang = "/".join(langs)
            break
        except (NoTranscriptFound, TranscriptsDisabled):
            continue
        except Exception:
            continue

    # 자동 생성 자막 (언어 무관)도 시도
    if not transcript_text:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            for t in transcript_list:
                fetched = t.fetch()
                transcript_text = " ".join(seg["text"].strip() for seg in fetched if seg["text"].strip())
                used_lang = t.language_code + "(자동생성)"
                break
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"자막을 찾을 수 없습니다. 자막이 비활성화된 영상이거나 비공개 영상일 수 있습니다. (video_id: {video_id})"
            )

    if not transcript_text:
        raise HTTPException(status_code=404, detail="자막 내용이 비어있습니다.")

    return {
        "video_id": video_id,
        "language": used_lang,
        "length": len(transcript_text),
        "transcript": transcript_text,
    }
