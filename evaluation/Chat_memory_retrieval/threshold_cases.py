chat_retrieval_cases = [
    {
        "case": "positive_001",
        "query": "I'm making breakfast and can't decide what to drink.",
        "expected_relevant": ["memory_001"],
    },
    {
        "case": "positive_002",
        "query": "I finally have some time to plan my trip for next spring.",
        "expected_relevant": ["memory_010"],
    },
    {
        "case": "positive_003",
        "query": "I've been sitting around too much lately. I really need to get moving again. should i start running?",
        "expected_relevant": ["memory_003"],
    },
    {
        "case": "positive_004",
        "query": "I'm heading out for dinner tonight and have no idea what to order.",
        "expected_relevant": ["memory_005", "memory_022"],
    },
    {
        "case": "positive_005",
        "query": "My phone is getting pretty old. I'm thinking it's time for a new one.",
        "expected_relevant": ["memory_015"],
    },
    {
        "case": "positive_006",
        "query": "I keep opening social media whenever I get bored. It's getting ridiculous.",
        "expected_relevant": ["memory_016"],
    },
    {
        "case": "positive_007",
        "query": "I've always wanted to learn guitar but never actually started.",
        "expected_relevant": ["memory_019"],
    },
    {
        "case": "positive_008",
        "query": "I have a presentation coming up and I'm already nervous about speaking in front of everyone.",
        "expected_relevant": ["memory_011"],
    },
    {
        "case": "positive_009",
        "query": "I'm trying to fix my sleep schedule because staying up so late isn't working anymore.",
        "expected_relevant": ["memory_027"],
    },
    {
        "case": "positive_010",
        "query": "I'm thinking about starting a little side business but don't know where to begin.",
        "expected_relevant": ["memory_021"],
    },
    {
        "case": "positive_011",
        "query": "I'm going on a trip and I'm wondering if I should just take the train instead of flying.",
        "expected_relevant": ["memory_020"],
    },
    {
        "case": "positive_012",
        "query": "I want to get better at photography but I'm not sure what I should practice first.",
        "expected_relevant": ["memory_029"],
    },
    {
        "case": "positive_013",
        "query": "I need to buy some clothes soon, but I don't want to end up buying a bunch of cheap stuff I'll never wear.",
        "expected_relevant": ["memory_030"],
    },
    {
        "case": "positive_014",
        "query": "I'm looking for an online course to learn digital marketing.",
        "expected_relevant": ["memory_024"],
    },
    {
        "case": "positive_015",
        "query": "I haven't visited my parents in a while and I feel like I should make some time for them.",
        "expected_relevant": ["memory_028"],
    },
    {
        "case": "borderline_001",
        "query": "got nothing planned for the weekend, any ideas?",
        "expected_relevant": ["memory_007", "memory_017", "memory_029"],
    },
    {
        "case": "borderline_002",
        "query": "thinking of getting back into reading, any good books?",
        "expected_relevant": ["memory_017"],
    },
    {
        "case": "borderline_003",
        "query": "where do you usually go when you really need to get some work done?",
        "expected_relevant": ["memory_008"],
    },
    {
        "case": "borderline_004",
        "query": "i should probably start exercising again. what would you suggest?",
        "expected_relevant": ["memory_003", "memory_023"],
    },
    {
        "case": "borderline_005",
        "query": "need something to watch tonight, got any suggestions?",
        "expected_relevant": ["memory_025"],
    },
    {
        "case": "borderline_006",
        "query": "my weekdays feel pretty unorganized lately, any way to make them easier?",
        "expected_relevant": ["memory_012", "memory_018"],
    },
    {
        "case": "borderline_007",
        "query": "might start learning a language, which one should i try?",
        "expected_relevant": ["memory_002"],
    },
    {
        "case": "borderline_008",
        "query": "i've been wanting to buy something expensive but i'm not sure if i should yet",
        "expected_relevant": ["memory_006"],
    },
    {
        "case": "negative_001",
        "query": "Can you help me figure out why my laptop keeps getting hot?",
        "expected_relevant": [],
    },
    {
        "case": "negative_002",
        "query": "my phone keeps freezing randomly, any idea why?",
        "expected_relevant": [],
    },
    {
        "case": "negative_003",
        "query": "How do I make my internet connection more stable?",
        "expected_relevant": [],
    },
    {
        "case": "negative_004",
        "query": "I'm trying to organize all the files on my computer and it's a complete mess.",
        "expected_relevant": [],
    },
    {
        "case": "negative_005",
        "query": "I have an exam coming up and I don't know how to study for it efficiently.",
        "expected_relevant": [],
    },
    {
        "case": "negative_006",
        "query": "I'm looking for a good way to clean my room faster.",
        "expected_relevant": [],
    },
    {
        "case": "negative_007",
        "query": "My headphones stopped working on one side. Any idea what could be wrong?",
        "expected_relevant": [],
    },
]