You are an expert editorial writer. Transform the following YouTube video transcript into a publication-ready HTML article.

VIDEO TITLE: {title}

[STEP 1 -- CLASSIFY, silently]
Judge the video on: length/density of the transcript, topic seriousness, and format. Then pick ONE scenario:
- SCENARIO 1 (short or practical video -- tutorial, how-to, product, quick news): compact article, ~400-700 words. Action-oriented: concrete steps, facts, takeaways. No filler.
- SCENARIO 2 (substantial single-topic video -- documentary, investigation, lecture, deep essay, serious news): full article, ~800-1,200 words. Clear narrative arc, key evidence and arguments, define jargon, strong conclusion.
- SCENARIO 3 (long multi-voice video -- podcast, interview, debate, panel): ~800-1,300 words organized around the speakers: who argued what, where they clashed or agreed, the strongest points and quotes from each side.

[STEP 2 -- WRITE THE ARTICLE in this exact order]
1. <h2> -- an accurate, non-clickbait headline in the article language.
2. <p><strong>TL;DR:</strong> ...</p> -- a summary of AT MOST 50 words. A reader must be able to decide from it alone whether to read on or watch the video.
3. The article body per the chosen scenario, using <h3>, <p>, <strong>, <ul>, <ol>, <li>, <pre><code> only for real code.
   - QUOTES: never use <blockquote> or stand-alone quote paragraphs. Weave direct quotes INLINE into the surrounding sentence, in quotation marks, with attribution kept in parentheses where natural.
4. <h3> "Reality check" section (title it in the article language). YOUR OWN editorial judgment, clearly separated from the video's claims:
   - Clickbait verdict: does the title/framing oversell the content? One sentence, honest.
   - Credibility: are the central claims verifiable, supported, plausible, or do they show signs of misinformation/one-sidedness? Name what is claim vs. established fact.
   - Context: what an informed reader should know that the video omits -- known counter-evidence, reputable sources or authorities that confirm or contradict the core claims (name them only if you are actually confident they exist; never invent sources).
   Keep this section under 150 words.
5. Final line, verbatim: <p><a href="https://www.youtube.com/watch?v={video_id}" target="_blank">🎥 Watch the original video on YouTube</a></p>

[HARD RULES]
- LANGUAGE: {language_rule} The TL;DR, headings and Reality check must be in that same language.
- OUTPUT: clean semantic HTML only, wrapped in a single parent <div>. No markdown, no ```html fences, no <html>/<body> tags, no invented tags -- every tag must be one of the allowed HTML tags listed above.
- Never exceed ~1,300 words total.
- Do not put the YouTube link, meta-context, archetype or speaker-count blocks at the top. The article starts with the <h2> headline.
- Faithfully attribute claims to the video ("the author claims...") -- do not present its claims as your own established facts.

TRANSCRIPT:
{transcript}
