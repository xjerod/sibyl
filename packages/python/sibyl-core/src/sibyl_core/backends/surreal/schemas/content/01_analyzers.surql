DEFINE ANALYZER IF NOT EXISTS content_analyzer
    TOKENIZERS blank, class
    FILTERS lowercase, ascii, snowball(english);

DEFINE ANALYZER IF NOT EXISTS title_analyzer
    TOKENIZERS blank, class
    FILTERS lowercase, ascii, snowball(english);

DEFINE ANALYZER IF NOT EXISTS code_analyzer
    TOKENIZERS class, camel
    FILTERS lowercase, ascii;
