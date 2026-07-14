import os
import re
import urllib.request
import subprocess
import json
import litellm
from dotenv import load_dotenv
from rss_builder import add_article_to_feed
from srt_cleaner import parse_srt

# Load local environment variables from .env file
load_dotenv()

# Configure Google credentials for Vertex AI (optional, fallback to standard litellm env vars)
google_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
if google_creds:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.expanduser(google_creds)

# Ensure environment PATH has common binary folders
os.environ["PATH"] = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:" + os.environ.get("PATH", "")

def extract_video_id(url):
    """Extracts the 11-character video ID from any standard YouTube URL."""
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def download_subtitles(video_id):
    """Downloads auto-generated English or Ukrainian/Russian subtitles using yt-dlp."""
    output_tpl = f"/tmp/yt_feed_{video_id}"
    
    langs = ["en", "uk", "ru"]
    srt_path = None
    
    # Try getting yt-dlp binary from environment or default to system PATH
    ytdlp_bin = os.environ.get("YT_DLP_PATH", "yt-dlp")
    
    for lang in langs:
        print(f"Attempting to download auto-subtitles for lang={lang}...")
        cmd = [
            ytdlp_bin,
            "--write-auto-subs",
            "--sub-lang", lang,
            "--skip-download",
            "--convert-subs", "srt",
            "-o", output_tpl,
            f"https://www.youtube.com/watch?v={video_id}"
        ]
        
        # Run quietly
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        expected_path = f"{output_tpl}.{lang}.srt"
        if os.path.exists(expected_path):
            print(f"Successfully downloaded {lang} subtitles!")
            srt_path = expected_path
            break
            
    return srt_path

def generate_summary_article(title, transcript, video_id):
    """Sends the clean transcript to an LLM via LiteLLM using the Sentient AI Prompting Protocol."""
    print(f"Synthesizing transcript using model={os.environ.get('LLM_MODEL', 'vertex_ai/gemini-2.5-flash-lite')}...")
    
    prompt = f"""You are a cognitive synthesis engine operating under the Sentient AI Cognitive Protocol. 
Your task is to analyze the following spoken transcript and transform it into a deeply insightful, structurally adapted, publication-ready written article.

---
[COGNITIVE STAGE 1: META-ANALYSIS & CHARACTERIZATION]
First, analyze the raw transcript and characterize the video along these axes:
- Video Type (e.g., Technical Lecture, Casual Podcast, Brief Tutorial, Investigative News, Narrative Vlog)
- Speaker Count & Dynamics (Single speaker monolog, structured Q&A, multi-speaker debate)
- Depth & Density (High density technical data vs. low-density entertainment/stories)
- Overall Tone & Vibe (Academic, humorous, conversational, urgent, instructional)

[COGNITIVE STAGE 2: ADAPTIVE STRUCTURING RULES]
Based on your Stage 1 characterization, dynamically adapt your HTML output structure:
1. For TECHNICAL TUTORIALS/BRIEF VIDEOS: Keep it highly action-oriented. Provide immediate step-by-step setup guides, raw code blocks if any, and direct "how-to" takeaways. Avoid verbose background filler.
2. For LONG PODCASTS/DEBATES: Focus heavily on speaker dynamics. Detail who argued what, outline contrasting perspectives, capture the flow of discussion, and write a cohesive narrative arc with deep synthesis.
3. For ACADEMIC/PHILOSOPHICAL LECTURES: Structure with detailed conceptual breakdowns, define core jargon/theories, explain historical/practical contexts, and provide a strong concluding summary.
4. For ENTERTAINMENT/HUMOR/TRAVEL: Focus on capturing the narrative energy, funny quotes, the journey's timeline, and the vibe. Use a lighter, more descriptive tone.

[COGNITIVE STAGE 3: GENERAL FORMATTING CONSTRAINTS]
- LANGUAGE RULES: 
  * If the transcript is in Ukrainian (uk), Russian (ru), Spanish (es), or English (en), write the article in that native language.
  * For ANY other language (such as Italian, French, German, Japanese, etc.), automatically translate and write the final article in English (en).
- Output ONLY clean, semantic HTML (enclosed in a parent <div>, using <h2>, <h3>, <h4>, <p>, <strong>, <ul>, <ol>, <li>, <blockquote>, <pre><code> for snippets).
- Do NOT output any markdown, ```html wrappers, or outer html/body tags.
- Include a small, subtle 2-line "Meta-Context" block at the very top using <em> detailing the detected video archetype, estimated speaker count, and tone. Include a clickable link to the video at the very top: '<p><a href="https://www.youtube.com/watch?v={video_id}" target="_blank">🎥 Watch original video on YouTube</a></p>'.

[COGNITIVE STAGE 4: SELF-CRITIQUE (ANTI-VANITY)]
Before outputting, review your generated summary. Ask yourself: "Where did I over-summarize? What subtle nuances or speaker disagreements did I flatten out?" Adjust your text to capture those missing layers of friction.

---
TRANSCRIPT:
{transcript}
"""

    model = os.environ.get("LLM_MODEL", "vertex_ai/gemini-2.5-flash-lite")

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        content = response.choices[0].message.content.strip()
        
        # Calculate token counts and cost telemetry (Gemini pricing fallback)
        try:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            # Input: $0.075 / 1M, Output: $0.30 / 1M
            cost = (prompt_tokens * 0.075 / 1000000) + (completion_tokens * 0.30 / 1000000)
            
            telemetry_line = f'<hr/><p style="font-size: 11px; color: #888; text-align: right;"><em>⚡ Summarized by {model} • Input: {prompt_tokens:,} tokens • Output: {completion_tokens:,} tokens • Est. Cost: ${cost:.6f}</em></p>'
            content += telemetry_line
        except Exception:
            pass
            
        return content
    except Exception as e:
        print(f"LiteLLM API call failed: {e}")
        return None

def process_youtube_video(url):
    """Complete Stage 2 pipeline: URL -> Subtitles -> Clean -> Gemini -> RSS Feed."""
    video_id = extract_video_id(url)
    if not video_id:
        print(f"Error: Invalid YouTube URL: {url}")
        return False
        
    print(f"\n--- Processing Video ID: {video_id} ---")
    
    # 1. Download auto subtitles
    srt_path = download_subtitles(video_id)
    if not srt_path:
        print("Error: Could not retrieve any subtitles for this video.")
        return False
        
    # 2. Parse and clean subtitles
    print("Parsing and cleaning subtitle file...")
    clean_transcript = parse_srt(srt_path)
    if not clean_transcript or len(clean_transcript) < 100:
        print("Error: Parsed transcript is empty or too short.")
        return False
        
    # Clean up temp file
    os.remove(srt_path)
    
    # 3. Generate article with Gemini
    # Let's get the video title first using yt-dlp
    try:
        ytdlp_bin = os.environ.get("YT_DLP_PATH", "yt-dlp")
        title_cmd = [ytdlp_bin, "--get-title", f"https://www.youtube.com/watch?v={video_id}"]
        video_title = subprocess.check_output(title_cmd, text=True).strip()
    except Exception:
        video_title = f"YouTube Video ({video_id})"
        
    print(f"Video Title: {video_title}")
    
    article_html = generate_summary_article(video_title, clean_transcript, video_id)
    if not article_html:
        return False
        
    # 4. Append to RSS feed
    # By using a custom article link prefix instead of the direct YouTube URL,
    # Feedly and other RSS clients will render the article text inline instead of
    # auto-redirecting to the YouTube app.
    article_link_prefix = os.environ.get("ARTICLE_LINK_PREFIX", "http://localhost:8090/article/")
    add_article_to_feed(
        title=f"AI Article: {video_title}",
        link=f"{article_link_prefix}{video_id}",
        html_content=article_html
    )
    print("Done! Check your feed now.")
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
        process_youtube_video(target_url)
    else:
        # Test fallback
        test_url = "https://www.youtube.com/watch?v=-MTSQjw5DrM"
        process_youtube_video(test_url)
