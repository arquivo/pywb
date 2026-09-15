.. _recorder:

Recorder
========

The recorder component acts a proxy component, intercepting requests to and response from the :ref:`warcserver` and recording them
to a WARC file on disk.

The recorder uses the :class:`pywb.recorder.multifilewarcwriter.MultiFileWARCWriter` which extends the base :class:`warcio.warcwriter.WARCWriter` from :mod:`warcio` and provides support for:

* appending to multiple WARC files at once

* WARC 'rollover' based on maximum size idle time

* indexing (CDXJ) on write


Many of the features of the Recorder are created for use with Webrecorder project, although the core recorder is used to provide
a basic recording via ``/record/`` endpoint. (See: :ref:`recording-mode`)


Deduplication Filters
---------------------

The core recorder class provides for optional deduplication using the :class:`pywb.recorder.redisindexer.WritableRedisIndexer` class which requires Redis to store the index, and can be used to either:

* write duplicates responses.

* write ``revisit`` records.

* ignore duplicates and don't write to WARC.


Custom Filtering
----------------

The recorder filter system also includes a filtering system to allow for not writing certain requests and responses.
Filters include:

* Skipping by regex applied to source (``Warcserver-Source-Coll`` header from Warcserver)

* Skipping if ``Recorder-Skip: 1`` header is provided

* Skipping if ``Range`` request header is provided

* Skipping if the target site's ``robots.txt`` disallows the configured ``robots_user_agent`` (see below)

* Filtering out certain HTTP headers, for example, http-only cookies

The additional recorder functionality will be enhanced in a future version.

For a more detailed examples, please consult the tests in :mod:`pywb.recorder.test.test_recorder`


Robots.txt Exclusion
---------------------

Two independent, optional settings are available in the ``recorder`` config section::

    recorder:
        source_coll: live
        robots_user_agent: Arquivo-web-crawler
        record_user_agent: "Mozilla/5.0 (compatible; Arquivo-web-crawler/1.0; +https://arquivo.pt/bot)"

``robots_user_agent``
    Enables robots.txt-based exclusion for record mode (eg. "archive page now"). Before
    persisting a capture, pywb fetches and checks the site's ``robots.txt`` for rules
    applying to this user agent token. If disallowed, the capture is not written to the WARC.
    The page is still served to the browser normally either way -- this only affects
    whether the capture is persisted, not whether it can be viewed live. If ``robots.txt``
    can't be fetched (eg. network error or timeout), the capture proceeds as if allowed, so
    a temporary robots.txt fetch failure never blocks archiving.

``record_user_agent``
    Overrides the outbound ``User-Agent`` sent for record-mode requests to the live site,
    instead of forwarding the browser's own ``User-Agent``. This is typically a longer,
    more descriptive string that includes the software name and version (as is customary
    for identifying a crawler), while ``robots_user_agent`` is the shorter token actually
    matched against the site's ``Disallow``/``Allow`` rules. When both are set, this
    ``User-Agent`` is also used when fetching ``robots.txt`` itself, so the site sees a
    consistent identity across all record-mode requests.

These two settings can be used independently: ``robots_user_agent`` alone gates persistence
without changing what's sent to the site, while ``record_user_agent`` alone changes the
outbound identity without any robots.txt-based persistence gating.



