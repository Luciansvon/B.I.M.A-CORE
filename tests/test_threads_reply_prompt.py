import core.threads_commands as tc


def test_threads_reply_prompt_contains_context_and_style_rules():
    prompt = tc._build_threads_reply_prompt(
        reply_username="user123",
        reply_text="wkwk relate bgt",
        post_text="laptop gua kipasnya udah kayak nyerah",
        viral_context="\n=== POLA VIRAL ===\npendek, punchy\n",
    )

    assert "@user123" in prompt
    assert "wkwk relate bgt" in prompt
    assert "laptop gua kipasnya udah kayak nyerah" in prompt
    assert "Balasan Buruk" in prompt
    assert "Balasan Baik" in prompt
    assert "Length matching" in prompt
    assert "No fluff" in prompt
    assert "Wah, menarik sekali" in prompt
    assert "Tentu" in prompt
    assert "lu" in prompt and "gua" in prompt


def test_threads_reply_prompt_short_comment_demands_short_reply():
    prompt = tc._build_threads_reply_prompt(
        reply_username="shortuser",
        reply_text="anjir wkwk",
        post_text="kopi dingin lebih jujur dari todo list gua",
    )

    assert "Komentar pendek" in prompt
    assert "maks 8 kata" in prompt
    assert "jangan jawab kayak customer service" in prompt
    assert "jangan bikin ceramah" in prompt
