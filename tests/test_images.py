import pytest
from pathlib import Path
from usi_scrapers.utils.images import clean_filename

def test_clean_filename_otodom_cdn():
    url = "https://ireland.apollo.olxcdn.com/v1/files/eyJpZCI6ImY1c2JyeTk0czUzei1BUEwifQ/image;s=1280x1024"
    assert clean_filename(url) == "eyJpZCI6ImY1c2JyeTk0czUzei1BUEwifQ.jpg"

def test_clean_filename_tabelaofert():
    url = "https://tabelaofert.pl/oferty/zdjecia/quality_70,scale_425x283,ID-32981-01_Budynek.jpg"
    assert clean_filename(url) == "32981-01_Budynek.jpg"

def test_clean_filename_standard():
    url = "https://example.com/images/building_123.png?v=123#hash"
    assert clean_filename(url) == "building_123.png"

def test_clean_filename_cachebuster():
    url = "https://example.com/assets/photo_e94b5737.webp"
    assert clean_filename(url) == "photo.webp"

def test_clean_filename_no_extension():
    # Fallback to .jpg
    url = "https://tabelaofert.pl/ID-123456"
    assert clean_filename(url) == "123456.jpg"
