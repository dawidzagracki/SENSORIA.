FROM postgres:16-bookworm AS polish-dictionary

# Debian libreoffice-dictionaries package is versioned and distributed under MPL-2.0.
RUN apt-get update \
    && apt-get install --no-install-recommends -y hunspell-pl=1:7.5.0-1 python3 \
    && rm -rf /var/lib/apt/lists/*
COPY docker/prepare-polish-dictionary.py /usr/local/bin/prepare-polish-dictionary.py
RUN python3 /usr/local/bin/prepare-polish-dictionary.py \
    && cp /usr/share/doc/hunspell-pl/copyright /out/COPYRIGHT

FROM postgres:16-alpine
COPY --from=polish-dictionary /out/sensoria_pl.affix /usr/local/share/postgresql/tsearch_data/sensoria_pl.affix
COPY --from=polish-dictionary /out/sensoria_pl.dict /usr/local/share/postgresql/tsearch_data/sensoria_pl.dict
COPY --from=polish-dictionary /out/sensoria_pl_folded.affix /usr/local/share/postgresql/tsearch_data/sensoria_pl_folded.affix
COPY --from=polish-dictionary /out/sensoria_pl_folded.dict /usr/local/share/postgresql/tsearch_data/sensoria_pl_folded.dict
COPY --from=polish-dictionary /out/COPYRIGHT /usr/share/doc/sensoria-polish-dictionary/COPYRIGHT
