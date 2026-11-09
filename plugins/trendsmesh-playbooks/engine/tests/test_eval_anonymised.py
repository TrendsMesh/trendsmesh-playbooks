"""The evals' anonymisation: check_anonymised.py finds a real Reddit user, post id, link or Goodreads
reader planted in an evals tree, and gen_mocks.py's LD scrub takes them out of texts.

The whole committed tree is checked by running the script itself (about a minute): see its docstring."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
LIB = PLUGIN / "evals" / "_lib"
CHECKER = LIB / "check_anonymised.py"


def _check(root: Path, examples: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(CHECKER), "--root", str(root), "--examples", str(examples)],
                       capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout


@pytest.fixture
def trees(tmp_path):
    """An evals tree to plant in and a folder of example runs: one Reddit post by a 3-character
    author, one comment, and one Goodreads text."""
    root, examples = tmp_path / "evals", tmp_path / "examples"
    (root / "case").mkdir(parents=True)
    (examples / "run" / "voice").mkdir(parents=True)
    (examples / "run" / "voice" / "reddit_posts.json").write_text(json.dumps({"data": [
        {"id": "1qqk4wd", "author": "Bob", "subreddit": "LucidDreaming", "title": "a post"},
        {"id": "ohq3x2k", "author": "Some_Reader_42", "subreddit": "LucidDreaming", "link_id": "t3_1zzq7ab",
         "parent_id": "t1_ohq0aaa", "body": "a comment"}]}), encoding="utf-8")
    (examples / "run" / "voice" / "goodreads_reviews.txt").write_text(
        "=== #1 | rating 5 | Dana Whitfield | review id kca://review:goodreads/amzn1.gr.review:goodreads.v1.Ab3dEf7H\n"
        "A good book.\n"
        "=== #2 | rating 4 | Kim | review id kca://review:goodreads/amzn1.gr.review:goodreads.v1.Xy9zQw2R\n"
        "=== #3 | rating 3 | moonvale | review id kca://review:goodreads/amzn1.gr.review:goodreads.v1.Pq8rSt4U\n",
        encoding="utf-8")
    return root, examples


def _plant(root: Path, text: str) -> None:
    """In a JSON answer's text, or a saved Goodreads text when it is a review's header."""
    if text.startswith("=== "):
        (root / "case" / "goodreads.txt").write_text(text + "\n", encoding="utf-8")
    else:
        (root / "case" / "fixture.json").write_text(json.dumps({"selftext": text}), encoding="utf-8")


def test_a_clean_tree_passes(trees):
    root, examples = trees
    _plant(root, "Night one: thanks u/creator and u/creator_0012, see https://example.com/r/3; Kim and Dana agree. "
                 "I write on Wattpad as creator.")
    _plant(root, "=== #1 | rating 5 | Reviewer 1 | review id review 1")   # (a first name alone is a word)
    code, out = _check(root, examples)
    assert code == 0, out


@pytest.mark.parametrize("planted, said", [
    ("shoutout to u/realname for this", "a Reddit user"),
    ("as /u/realname wrote", "a Reddit user"),
    ("I write on Wattpad as NightOwlWriter.", "a pen name"),     # a name the poster gives on another site
    ("[View Poll](https://www.reddit.com/poll/1pollzz)", "a Reddit link"),
    ("see reddit.com/r/LucidDreaming/comments/1abcdef/x", "a Reddit link"),
])
def test_a_reddit_user_or_link_in_a_text_fails(trees, planted, said):
    root, examples = trees
    _plant(root, planted)
    code, out = _check(root, examples)
    assert code == 1 and said in out, out


@pytest.mark.parametrize("planted, said", [
    ("the post 1qqk4wd", "original id"),           # a 7-character post id
    ("its thread t3_1zzq7ab", "original id"),       # a post id named by a comment
    ("parent ohq0aaa", "original id"),
    ("as bob said", "creator handle"),              # a 3-character Reddit author, in any case
    ("Dana Whitfield liked it", "creator handle"),    # a Goodreads reader's full name
    ("as Moonvale wrote", "creator handle"),         # a Goodreads reader's handle-like name
    ("review Ab3dEf7H", "original id"),
    ("=== #1 | rating 5 | Dana | review id review 1", "a Goodreads header"),   # a header not scrubbed
    ("=== #1 | rating 5 | Reviewer 1 | review id abc123XYZ", "a Goodreads header"),
])
def test_an_original_reddit_id_author_or_goodreads_reader_fails(trees, planted, said):
    root, examples = trees
    _plant(root, planted)
    code, out = _check(root, examples)
    assert code == 1 and said in out, out


def _gen_mocks():
    sys.path.insert(0, str(LIB))
    try:
        spec = importlib.util.spec_from_file_location("gen_mocks_under_test", LIB / "gen_mocks.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(LIB))


@pytest.mark.private_data
def test_the_ld_scrub_takes_reddit_users_and_links_out_of_texts():
    gm = _gen_mocks()
    a = gm.LdAnon(())
    a.author("Known_Author")
    a.author("Bob")
    assert a.text("Lately I post my stories on Wattpad as NightOwlWriter.  My writing") == (
        "Lately I post my stories on Wattpad as creator.  My writing")
    text = a.text("thanks u/Known_Author and /u/Stranger_12, bob agreed; "
                  "[View Poll](https://www.reddit.com/poll/1pollzz) and https://old.reddit.com/r/x/comments/1abcdef/y")
    assert "Known_Author" not in text and "Stranger_12" not in text and "bob" not in text.lower()
    assert "thanks u/creator_0001 and u/creator, creator_0002 agreed" in text
    assert "reddit.com" not in text and "1pollzz" not in text and "1abcdef" not in text
    assert text.count("https://example.com/r/") == 2


LD = PLUGIN.parents[1] / "handoff" / "creative-brief_v02" / "examples" / "ld-en-dry-run"


@pytest.mark.private_data
@pytest.mark.skipif(not LD.is_dir(), reason="the creative brief handoff's LD dry run is not in this checkout")
def test_no_brand_word_of_the_ld_dry_run_is_in_the_evals():
    """The product, its landing page (and the host's first label), the ad account and the campaigns'
    brand word: none in a committed eval file (the A1 targeting read and the G1 mock included)."""
    gm = _gen_mocks()
    olds = {old for old, _ in gm.ld_brand(LD)}
    host = next(old for old, new in gm.ld_brand(LD) if new == gm.LD_DOMAIN)
    olds.add(host.split(".", 1)[0])
    evals = PLUGIN / "evals"
    hits = [f"{p.relative_to(evals)}: {old[:6]}..." for p in evals.rglob("*")
            if p.is_file() and "results" not in p.relative_to(evals).parts and p.suffix in {".json", ".md", ".py", ".txt"}
            for old in olds if old in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits == []
