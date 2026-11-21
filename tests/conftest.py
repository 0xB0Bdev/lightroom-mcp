"""Shared fixtures: a tiny SQLite file shaped like a Lightroom catalog."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SCHEMA = """
CREATE TABLE Adobe_images (id_local INTEGER PRIMARY KEY, id_global, captureTime, colorLabels, copyName, fileFormat,
    fileHeight, fileWidth, masterImage, pick, rating, rootFile);
CREATE TABLE AgLibraryFile (id_local INTEGER PRIMARY KEY, baseName, extension, folder);
CREATE TABLE AgLibraryFolder (id_local INTEGER PRIMARY KEY, pathFromRoot, rootFolder);
CREATE TABLE AgLibraryRootFolder (id_local INTEGER PRIMARY KEY, absolutePath);
CREATE TABLE AgHarvestedExifMetadata (id_local INTEGER PRIMARY KEY, image, aperture, cameraModelRef,
    focalLength, isoSpeedRating, lensRef, shutterSpeed);
CREATE TABLE AgInternedExifCameraModel (id_local INTEGER PRIMARY KEY, value);
CREATE TABLE AgInternedExifLens (id_local INTEGER PRIMARY KEY, value);
CREATE TABLE AgLibraryKeyword (id_local INTEGER PRIMARY KEY, name, lc_name, parent);
CREATE TABLE AgLibraryKeywordImage (id_local INTEGER PRIMARY KEY, image, tag);
CREATE TABLE AgLibraryCollection (id_local INTEGER PRIMARY KEY, creationId, name, parent);
CREATE TABLE AgLibraryCollectionImage (id_local INTEGER PRIMARY KEY, collection, image);
CREATE TABLE AgLibraryIPTC (id_local INTEGER PRIMARY KEY, caption, copyright, image);
CREATE TABLE Adobe_imageDevelopSettings (id_local INTEGER PRIMARY KEY, image, text, processVersion,
    hasDevelopAdjustmentsEx);

INSERT INTO AgLibraryRootFolder VALUES (1, '/Photos/');
INSERT INTO AgLibraryFolder VALUES (1, '2026/trip/', 1);
INSERT INTO AgInternedExifCameraModel VALUES (1, 'Canon EOS 6D'), (2, 'iPhone 17 Pro');
INSERT INTO AgInternedExifLens VALUES (1, 'EF100mm f/2.8L Macro IS USM');

INSERT INTO AgLibraryFile VALUES (1, 'IMG_0001', 'CR2', 1), (2, 'IMG_0002', 'CR2', 1), (3, 'phone_100%', 'jpg', 1);
INSERT INTO Adobe_images VALUES
    (10, 'UUID-10', '2026-01-05T10:00:00', 'Red', NULL, 'RAW', 3648.0, 5472.0, NULL, 1.0, 5.0, 1),
    (11, 'UUID-11', '2026-02-10T12:30:00', '',    NULL, 'RAW', 3648.0, 5472.0, NULL, -1.0, 2.0, 2),
    (12, 'UUID-12', '2026-03-15T09:15:00', NULL,  NULL, 'JPG', 4032.0, 2268.0, NULL, NULL, NULL, 3),
    (13, 'UUID-13', '2026-01-05T10:00:00', '',    'Copy 1', 'RAW', 3648.0, 5472.0, 10, 0.0, 3.0, 1);
INSERT INTO AgHarvestedExifMetadata VALUES
    (1, 10, 6.918863, 1, 100.0, 100.0, 1, 1.0),
    (2, 11, 4.0, 1, 100.0, 400.0, 1, 6.906891),
    (3, 12, 2.0, 2, 6.8, 64.0, NULL, -1.0);

INSERT INTO AgLibraryKeyword VALUES (1, NULL, NULL, NULL), (2, 'Macro', 'macro', 1), (3, 'Travel', 'travel', 1);
INSERT INTO AgLibraryKeywordImage VALUES (1, 10, 2), (2, 10, 3), (3, 11, 3);
INSERT INTO AgLibraryCollection VALUES
    (20, 'com.adobe.ag.library.collection', 'Best Of', NULL),
    (21, 'com.adobe.ag.library.smart_collection', 'Five Stars', NULL),
    (22, 'com.adobe.ag.print.unsaved', 'Unsaved Print', NULL);
INSERT INTO AgLibraryCollectionImage VALUES (1, 20, 10), (2, 20, 12);
INSERT INTO AgLibraryIPTC VALUES (1, 'A caption', '(c) Me', 10);
INSERT INTO Adobe_imageDevelopSettings VALUES
    (1, 10, 's = { Exposure2012 = 0.5,
Contrast2012 = -10,
CameraProfile = "Adobe Standard",
EnableColorAdjustments = true,
ToneCurvePV2012 = { 0, 0, 255, 255 },
Look = { Name = "Vivid", Amount = 1 } }', 11.0, 1);
"""


@pytest.fixture
def catalog_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "Test Catalog.lrcat"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setenv("LIGHTROOM_CATALOG", str(path))
    return path
