import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from zoneinfo import ZoneInfo

from src.app.config import settings
from src.app.utils.logger import logger

class SocialContentService:
    """
    Automated Multi-Platform Social Media & Developer Branding Content Engine.
    Transforms raw video intelligence into high-conversion, SEO-optimized,
    platform-native posts ready for 1-click copying and publishing.
    
    Platforms Supported:
    1. LinkedIn (Thought Leadership & Executive Carousel / Post)
    2. Twitter / X (High-Engagement Viral Thread + Hook Tweet)
    3. Dev.to / Hashnode / GitHub Discussions (Complete Markdown Tech Article)
    4. Medium (In-Depth Technical Story & Commentary)
    5. Reddit / Hacker News (Raw Technical TL;DR & Discussion Prompt)
    """

    @classmethod
    def sanitize_filename(cls, text: str) -> str:
        """Removes illegal Windows characters from filenames."""
        cleaned = re.sub(r'[\\/*?:"<>|]', "", text)
        cleaned = re.sub(r'\.{2,}', '', cleaned)
        cleaned = re.sub(r'\s+', " ", cleaned).strip().strip('. ')
        return cleaned[:100]

    @classmethod
    def format_linkedin_post(
        cls,
        video_title: str,
        channel_name: str,
        one_sentence: str,
        overview: str,
        key_takeaways: List[str],
        action_items: List[str],
        video_url: str,
        category: str
    ) -> str:
        """
        Formats a high-engagement LinkedIn post optimized for developer branding,
        algorithmic dwell time, and clean professional readability.
        """
        bullets = "\n".join([f"🔹 {pt}" for pt in key_takeaways[:4]])
        actions = "\n".join([f"✅ {act}" for act in action_items[:2]]) if action_items else ""

        # Category hashtags
        hashtags = "#SoftwareEngineering #WebDevelopment #ArtificialIntelligence #TechTrends #Programming #DeveloperProductivity"

        return f"""🚀 BREAKING DOWN: {video_title}

{one_sentence}

Here is what every software engineer and tech leader needs to understand about this latest update from {channel_name}:

━━━━━━━━━━━━━━━━━━━━
📌 Context & Overview:
{overview}

━━━━━━━━━━━━━━━━━━━━
💡 Key Architectural & Industry Takeaways:
{bullets}

{f"━━━━━━━━━━━━━━━━━━━━\n🎯 Actionable Takeaways for Developers:\n{actions}\n" if actions else ""}
━━━━━━━━━━━━━━━━━━━━
💬 What is your perspective on this? Are you seeing this shift in your current stack or organization? Drop your thoughts below!

🔗 Original Deep Dive Video: {video_url}

{hashtags}
"""

    @classmethod
    def format_twitter_thread(
        cls,
        video_title: str,
        channel_name: str,
        one_sentence: str,
        overview: str,
        key_takeaways: List[str],
        action_items: List[str],
        video_url: str
    ) -> str:
        """
        Formats an algorithmic Twitter / X thread with strong hook, numbered points,
        and final retweet/bookmark call-to-action.
        """
        tweets = []

        # Tweet 1: Hook
        t1 = f"""🧵 1/5 The tech world moves fast. Here's what just broke in software & AI:

"{video_title}" via {channel_name}

TL;DR: {one_sentence}

Full breakdown below 👇"""
        tweets.append(t1)

        # Tweet 2: Context
        t2 = f"""2/5 🎯 The Big Picture:

{overview[:250]}"""
        tweets.append(t2)

        # Tweet 3: Core Takeaways
        t3_bullets = "\n".join([f"• {pt[:120]}" for pt in key_takeaways[:3]])
        t3 = f"""3/5 ⚡ 3 Crucial Insights:

{t3_bullets}"""
        tweets.append(t3)

        # Tweet 4: Action Items
        if action_items:
            act_bullets = "\n".join([f"→ {act[:120]}" for act in action_items[:2]])
            t4 = f"""4/5 🛠️ What Developers Should Do Next:

{act_bullets}"""
            tweets.append(t4)
        else:
            tweets.append(f"""4/5 🔍 Why It Matters: This signals where the modern tech ecosystem is heading over the next 12-24 months.""")

        # Tweet 5: Conclusion & Link
        t5 = f"""5/5 📌 Summary: Stay ahead of the curve.

Watch the full breakdown by {channel_name}:
{video_url}

If you found this valuable:
1. Retweet the first tweet to share with developers
2. Follow me for daily high-signal tech updates 🚀"""
        tweets.append(t5)

        return "\n\n" + ("=" * 45) + "\n\n".join([f"--- [TWEET {idx+1}] ---\n{t}" for idx, t in enumerate(tweets)])

    @classmethod
    def format_devto_article(
        cls,
        video_title: str,
        channel_name: str,
        one_sentence: str,
        overview: str,
        key_takeaways: List[str],
        detailed_breakdown: str,
        action_items: List[str],
        video_url: str
    ) -> str:
        """
        Formats a complete, SEO-friendly Dev.to / Hashnode markdown post
        with frontmatter tags ready for instant publishing.
        """
        bullets = "\n".join([f"- **{pt}**" if not pt.startswith("**") else f"- {pt}" for pt in key_takeaways])
        actions = "\n".join([f"- {act}" for act in action_items]) if action_items else "- Keep track of upstream updates."

        clean_slug = re.sub(r'[^a-zA-Z0-9]', '-', video_title.lower()).strip('-')[:50]

        return f"""---
title: "{video_title} - Developer Executive Briefing"
published: true
description: "{one_sentence[:140]}"
tags: programming, webdev, ai, technology
cover_image: 
canonical_url: 
---

# {video_title}

> **Executive Summary:** {one_sentence}  
> **Source Channel:** [{channel_name}]({video_url})

---

## 🎯 Context & Overview

{overview}

---

## ⚡ Key Architectural & Technical Takeaways

{bullets}

---

## 🔬 In-Depth Analysis

{detailed_breakdown}

---

## 🛠️ Practical Action Items for Developers

{actions}

---

## 💭 Discussion

What are your thoughts on this direction? Are you adopting this in your projects? Let's discuss in the comments below!

*Originally referenced from [{channel_name}'s breakdown]({video_url}).*
"""

    @classmethod
    def format_medium_story(
        cls,
        video_title: str,
        channel_name: str,
        one_sentence: str,
        overview: str,
        key_takeaways: List[str],
        detailed_breakdown: str,
        action_items: List[str],
        video_url: str
    ) -> str:
        """
        Formats a Medium-optimized article focusing on storytelling,
        clear section breaks, and thought-leadership insights.
        """
        bullets = "\n\n".join([f"• **{pt}**" if not pt.startswith("**") else f"• {pt}" for pt in key_takeaways])

        return f"""# {video_title}: An Executive Breakdown for Modern Engineers

### By a Software Engineer tracking the frontier of technology

---

## The Bottom Line
> {one_sentence}

In today's fast-moving software ecosystem, staying on top of technical shifts is what separates junior coders from senior architects. Recently, **{channel_name}** released an essential technical overview titled **"{video_title}"**. Here is the high-signal, zero-fluff breakdown.

---

## The Big Picture: Context & Relevance
{overview}

---

## Core Technical & Strategic Takeaways
{bullets}

---

## Deep Dive & Architectural Considerations
{detailed_breakdown}

---

## What This Means for Your Next Sprint
{chr(10).join([f"- {a}" for a in action_items]) if action_items else "- Audit your current dependencies and tooling."}

---

*Full Video Reference: [{video_title} on YouTube]({video_url})*
"""

    @classmethod
    def format_reddit_hn_post(
        cls,
        video_title: str,
        channel_name: str,
        one_sentence: str,
        overview: str,
        key_takeaways: List[str],
        video_url: str
    ) -> str:
        """
        Formats a no-nonsense, high-signal post for r/programming, r/webdev,
        or Hacker News comments/discussions.
        """
        bullets = "\n".join([f"* {pt}" for pt in key_takeaways[:4]])

        return f"""**Title:** [Breakdown] {video_title} ({channel_name})

**TL;DR:** {one_sentence}

**Context:**
{overview}

**Key Points:**
{bullets}

**Discussion Link:** {video_url}

Curious to hear the community's thoughts on how this affects production architecture.
"""

    @classmethod
    def generate_and_save_social_suite(
        cls,
        video_title: str,
        channel_name: str,
        video_url: str,
        video_id: str,
        summary_data: Dict[str, Any]
    ) -> Path:
        """Generates and saves a set of platform-specific social content files."""
        clean_title = cls.sanitize_filename(video_title) or f"post_{video_id}"
        file_path = dest_dir / f"{clean_title}.md"

        one_sentence = summary_data.get("one_sentence_takeaway", "")
        overview = summary_data.get("context_and_overview", "")
        key_takeaways = summary_data.get("key_takeaways", [])
        detailed_breakdown = summary_data.get("detailed_breakdown", "")
        action_items = summary_data.get("action_items", [])
        category = summary_data.get("category", "general_tech")

        # Build individual platform variations
        linkedin_text = cls.format_linkedin_post(
            video_title, channel_name, one_sentence, overview, key_takeaways, action_items, video_url, category
        )
        twitter_text = cls.format_twitter_thread(
            video_title, channel_name, one_sentence, overview, key_takeaways, action_items, video_url
        )
        devto_text = cls.format_devto_article(
            video_title, channel_name, one_sentence, overview, key_takeaways, detailed_breakdown, action_items, video_url
        )
        medium_text = cls.format_medium_story(
            video_title, channel_name, one_sentence, overview, key_takeaways, detailed_breakdown, action_items, video_url
        )
        reddit_text = cls.format_reddit_hn_post(
            video_title, channel_name, one_sentence, overview, key_takeaways, video_url
        )

        master_doc = f"""# 🚀 1-Click Social Media & Developer Branding Suite

> 📌 **Video Title:** {video_title}  
> 📺 **Channel:** {channel_name} | 🔗 [Watch on YouTube]({video_url})  
> ⏱️ **Generated:** {now_pkt.strftime("%A, %d %b %Y - %I:%M %p PKT")}  
> 💼 **Purpose:** Instant 1-click copy-paste content optimized for personal branding, SEO, and authority.

---

# 📱 1. LINKEDIN POST (Executive & Thought Leadership)
*Instructions: Copy the block below and paste directly into LinkedIn as a post.*

```text
{linkedin_text.strip()}
```

---

# 🐦 2. TWITTER / X THREAD (Viral Dev Hook)
*Instructions: Copy and post as a 5-tweet thread on Twitter / X.*

```text
{twitter_text.strip()}
```

---

# 💻 3. DEV.TO / HASHNODE ARTICLE (Complete Markdown Post)
*Instructions: Click "Write a Post" on Dev.to or Hashnode, switch to Markdown mode, and paste.*

```markdown
{devto_text.strip()}
```

---

# 📖 4. MEDIUM STORY (In-Depth Technical Story)
*Instructions: Copy the text below and paste into Medium's editor.*

```markdown
{medium_text.strip()}
```

---

# 👾 5. REDDIT / HACKER NEWS (Tech TL;DR & Community Discussion)
*Instructions: Paste into relevant subreddits (e.g. r/programming, r/webdev, r/technology) or Hacker News.*

```text
{reddit_text.strip()}
```
"""

        file_path.write_text(master_doc, encoding="utf-8")
        logger.info(f"Generated 1-Click Social Media Suite: {file_path}")

        return file_path

    

        header = """# 📱 Social Media Ready-to-Publish Catalog

This directory contains pre-formatted, platform-tailored content (LinkedIn, Twitter/X, Dev.to, Medium, Reddit) generated automatically from your YouTube subscriptions.

| Date | Channel | Topic / Post Title | 1-Click Copy File |
| :--- | :--- | :--- | :--- |
"""
        existing_content = ""
        if index_file.exists():
            existing_content = index_file.read_text(encoding="utf-8")
        else:
            existing_content = header

        row = f"| {today_str} | {channel_name} | {video_title[:60]} | [{clean_title}]({rel_link}) |\n"
        if row not in existing_content:
            existing_content += row
            index_file.write_text(existing_content, encoding="utf-8")

    @classmethod
    def generate_omnichannel_social_suite(
        cls,
        topic_title: str,
        platforms: List[str],
        sources: List[str],
        analysis: Dict[str, Any]
    ) -> Path:
        """Generates a publishing suite for an omnichannel topic cluster."""

        clean_title = cls.sanitize_filename(topic_title)
        topic_dir = folder / clean_title
        topic_dir.mkdir(parents=True, exist_ok=True)

        exec_summary = analysis.get("executive_summary", "")
        feature_specs = "\n".join([f"• {f}" for f in analysis.get("feature_release_details", [])[:3]])
        industry_impact = "\n".join([f"• {i}" for i in analysis.get("industry_impact", [])[:2]])
        community_sentiment = "\n".join([f"• {c}" for c in analysis.get("community_reaction", [])[:3]])
        tech_takeaways = "\n".join([f"• {t}" for t in analysis.get("technical_takeaways", [])[:3]])

        # 1. LinkedIn Post
        linkedin_text = f"""🚀 TECH & AI INTELLIGENCE BRIEF: {topic_title}

{exec_summary}

Across the tech ecosystem (tracked on {', '.join(platforms).upper()}):

━━━━━━━━━━━━━━━━━━━━
🔬 Technical Specifications & Core Features:
{feature_specs}

━━━━━━━━━━━━━━━━━━━━
🏢 Industry & Enterprise Impact:
{industry_impact}

━━━━━━━━━━━━━━━━━━━━
💬 Community & Developer Sentiment:
{community_sentiment}

━━━━━━━━━━━━━━━━━━━━
⚡ Key Technical Takeaways for Builders:
{tech_takeaways}

What are your thoughts on this breakthrough? How are you preparing your engineering stack for this?

#ArtificialIntelligence #SoftwareEngineering #TechNews #MachineLearning #DeveloperCommunity #OpenSource
"""
        (topic_dir / "linkedin_post.txt").write_text(linkedin_text, encoding="utf-8")

        # 2. Twitter / X Thread
        twitter_tweets = [
            f"1/5 🧵 BREAKING: {topic_title}\n\n{exec_summary[:220]}\n\nHere is everything you need to know from across {', '.join(platforms).upper()} 👇",
            f"2/5 🔬 Technical Highlights:\n\n{feature_specs[:240]}",
            f"3/5 🏢 Industry & Developer Impact:\n\n{industry_impact[:240]}",
            f"4/5 💬 What the Community is Saying (HN/Reddit/X):\n\n{community_sentiment[:240]}",
            f"5/5 ⚡ Technical Takeaways:\n\n{tech_takeaways[:220]}\n\nRT if helpful. Follow for automated daily tech & AI intelligence digests!"
        ]
        (topic_dir / "x_twitter_thread.txt").write_text("\n\n---\n\n".join(twitter_tweets), encoding="utf-8")

        # 3. Reddit Technical Post
        reddit_text = f"""[Discussion / News] {topic_title}

**Executive Summary:**
{exec_summary}

**Technical Specifications & What's New:**
{feature_specs}

**Developer & Industry Impact:**
{industry_impact}

**Community Sentiment & Ongoing Debate:**
{community_sentiment}

**Technical Takeaways:**
{tech_takeaways}

**Sources Ingested:** {', '.join(sources)}
What are your thoughts on this?
"""
        (topic_dir / "reddit_post.txt").write_text(reddit_text, encoding="utf-8")

        # 4. Discord / Slack Broadcast Bulletin
        bulletin_text = f"""📢 **TECH & AI INTELLIGENCE UPDATE: {topic_title}**
> {exec_summary}

**🔬 Key Highlights:**
{feature_specs}

**💬 Community Reaction:**
{community_sentiment}

**⚡ Engineering Takeaways:**
{tech_takeaways}

*Ingested from: {', '.join(sources)}*
"""
        (topic_dir / "discord_slack_bulletin.txt").write_text(bulletin_text, encoding="utf-8")

        # Master suite file
        master_file = topic_dir / "FULL_SOCIAL_SUITE.md"
        master_file.write_text(f"""# 📱 Social Content Suite: {topic_title}
> Generated on {datetime.now().strftime('%Y-%m-%d %H:%M PKT')} | Platforms: {', '.join(platforms).upper()}

## 1. LinkedIn Post
```text
{linkedin_text}
```

## 2. Twitter / X Thread
```text
{"\n\n---\n\n".join(twitter_tweets)}
```

## 3. Reddit Post
```markdown
{reddit_text}
```

## 4. Discord / Slack Bulletin
```text
{bulletin_text}
```
""", encoding="utf-8")

        cls._update_social_index(clean_title, "+".join(platforms).upper(), topic_title, today_str, master_file)
        logger.info(f"Generated Omnichannel Social Suite: {topic_dir}")
        return master_file

    @classmethod
    def format_omnichannel_dual_output(cls, report_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Formats intelligence cluster into exact Section A (.md) and Section B (Social Snippets) standards:
        - Section A: Clean Structured Markdown Output (.md)
        - Section B: 1-Click Platform Social Snippets (X Thread, LinkedIn, Reddit)
        """
        title = report_data.get("topic_title", "High-Impact Tech Headline")
        date_str = report_data.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
        category = report_data.get("category_display", report_data.get("category", "Artificial Intelligence"))
        platforms = report_data.get("platforms", ["X", "GitHub", "YouTube", "Hacker News"])
        sources = report_data.get("sources", ["Official Source", "Developer Docs"])
        exec_summary = report_data.get("executive_summary", "Overview highlighting the primary news, launch, or event.")

        # Key Technical Takeaways
        features = report_data.get("feature_release_details", [])
        impact = report_data.get("industry_impact", [])
        reaction = report_data.get("community_reaction", [])
        
        details_specs = " ".join(features[:2]) if features else "Core model specs, API changes, and software updates released."
        industry_imp = " ".join(impact[:2]) if impact else "Operational implications for developers, teams, and enterprises."
        comm_react = " ".join(reaction[:2]) if reaction else "Key viewpoints gathered from X, Reddit, and Hacker News."

        links_str = ", ".join([f"[{src}]({src})" if src.startswith("http") else src for src in sources[:3]])

        # SECTION A: Clean Structured Markdown Output (.md)
        section_a = f"""# {title}

**Date:** {date_str}  
**Category:** {category}  
**Source Platforms:** {', '.join(platforms)}  
**Original Links:** {links_str}  

---

## Executive Summary
{exec_summary}

## Key Technical Takeaways
* **Details & Specs:** {details_specs}
* **Industry Impact:** {industry_imp}
* **Community Reaction:** {comm_react}
"""

        # SECTION B: 1-Click Platform Social Snippets
        key_point_1 = features[0] if features else "Breakthrough performance benchmarks confirmed."
        key_point_2 = impact[0] if impact else "Enables zero-latency local agent execution."
        key_point_3 = reaction[0] if reaction else "Strong positive reception across the open-source community."
        source_link = sources[0] if sources else "https://github.com"

        x_thread = f"""=== X (TWITTER) THREAD FORMAT ===
1/ 🚨 {title}
{exec_summary[:180]}

2/ Key Details:
• {key_point_1}
• {key_point_2}
• {key_point_3}

3/ Read source / documentation: {source_link} #AI #TechNews #SoftwareEngineering"""

        linkedin_post = f"""=== LINKEDIN PROFESSIONAL FORMAT ===
{title}

{exec_summary}

Industry Implications & Operational Impact:
{industry_imp}

Key Takeaways:
🔹 {key_point_1}
🔹 {key_point_2}
🔹 {key_point_3}

What are your thoughts on this update? 

#SoftwareEngineering #TechTrends #ArtificialIntelligence #Innovation"""

        reddit_post = f"""=== REDDIT / COMMUNITY POST FORMAT ===
Title: {title}
Body:
- Summary: {exec_summary}
- Technical Changes & Architecture Details: {details_specs}
- Industry & Developer Impact: {industry_imp}
- Primary Source Links for Community Evaluation: {source_link}"""

        section_b = f"""{x_thread}

{linkedin_post}

{reddit_post}"""

        return {
            "section_a_markdown": section_a,
            "section_b_social": section_b,
            "x_thread": x_thread,
            "linkedin_post": linkedin_post,
            "reddit_post": reddit_post
        }
