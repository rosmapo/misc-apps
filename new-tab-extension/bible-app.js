/* =======================================================================================
   BIBLE APP - JavaScript (Finálna verzia: Implementácia vyhľadávania + funkčné odkazy + HISTÓRIA + ZÁLOŽKY)
   ======================================================================================= */

class BibleApp {
    constructor() {
        this.modal = document.getElementById('bibleModal');
        this.mainContent = document.getElementById('bibleMainContent');
        this.bookSelect = document.getElementById('bibleBookSelect');
        this.chapterSelect = document.getElementById('bibleChapterSelect');
        this.prevBtn = document.getElementById('prevChapterBtn');
        this.nextBtn = document.getElementById('nextChapterBtn');
        
        // Vyhľadávacie elementy
        this.searchInput = document.getElementById('bibleSearchInput');
        this.searchScopeSelect = document.getElementById('bibleSearchScope');
        this.searchBtn = document.getElementById('bibleSearchBtn'); 

        // [NOVÉ] Elementy histórie
        this.historyBackBtn = document.getElementById('bibleHistoryBackBtn');
        this.historyFwdBtn = document.getElementById('bibleHistoryFwdBtn');

        // Elementy pre záložky
        this.bookmarksBtn = document.getElementById('bibleBookmarksBtn');
        this.bookmarksModal = document.getElementById('bookmarksModal');
        this.verseContextMenu = document.getElementById('verseContextMenu');

        this.bibleData = null; 
        this.commentaryData = {}; 
        this.bookmarks = {}; // Formát: { "bookID:chapter:verse": { reference, verse, note } }

        this.currentBookID = null;
        this.currentChapter = null; 

        // [NOVÉ] Vlastnosti pre správu histórie
        this.navigationHistory = []; // Zásobník stavov
        this.historyIndex = -1;      // Aktuálna pozícia v zásobníku
        this.isNavigatingHistory = false; // Príznak, aby sme zabránili rekurzii

        this.initEventListeners();
        this.initData(); 
    }

    initEventListeners() {
        document.getElementById('bibleCloseBtn').addEventListener('click', () => this.close());
        this.prevBtn.addEventListener('click', () => this.navigateChapter(-1));
        this.nextBtn.addEventListener('click', () => this.navigateChapter(1));
        this.bookSelect.addEventListener('change', () => this.handleBookChange());
        this.chapterSelect.addEventListener('change', () => this.handleChapterChange());
        
        if (this.searchBtn) {
            this.searchBtn.addEventListener('click', () => this.performSearch());
        }
        if (this.searchInput) {
            this.searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.performSearch();
                }
            });
        }

        // [NOVÉ] Event Listeners pre históriu
        if (this.historyBackBtn) {
            this.historyBackBtn.addEventListener('click', () => this.navigateHistory(-1));
        }
        if (this.historyFwdBtn) {
            this.historyFwdBtn.addEventListener('click', () => this.navigateHistory(1));
        }

        // Event Listeners pre záložky
        if (this.bookmarksBtn) {
            this.bookmarksBtn.addEventListener('click', () => this.openBookmarksModal());
        }

        // Skrytie kontextového menu pri kliknutí mimo
        document.addEventListener('click', (e) => {
            if (this.verseContextMenu && !this.verseContextMenu.contains(e.target)) {
                this.hideVerseContextMenu();
            }
        });

        // Zabrániť defaultnému kontextovému menu v biblickom okne
        if (this.mainContent) {
            this.mainContent.addEventListener('contextmenu', (e) => {
                const verseLine = e.target.closest('.verse-line');
                if (verseLine) {
                    e.preventDefault();
                    this.showVerseContextMenu(e, verseLine);
                }
            });
        }
    }

    // =========================================================================
    // ZÁLOŽKY - ZÁKLADNÉ FUNKCIE
    // =========================================================================

    loadBookmarks() {
        const stored = localStorage.getItem('bibleBookmarks');
        if (stored) {
            try {
                this.bookmarks = JSON.parse(stored);
            } catch (e) {
                console.error('Chyba pri načítaní záložiek:', e);
                this.bookmarks = {};
            }
        }
    }

    saveBookmarks() {
        localStorage.setItem('bibleBookmarks', JSON.stringify(this.bookmarks));
    }

    getBookmarkKey(bookID, chapter, verse) {
        return `${bookID}:${chapter}:${verse}`;
    }

    hasBookmark(bookID, chapter, verse) {
        const key = this.getBookmarkKey(bookID, chapter, verse);
        return !!this.bookmarks[key];
    }

    addBookmark(bookID, chapter, verse, verseText, reference) {
        const key = this.getBookmarkKey(bookID, chapter, verse);
        this.bookmarks[key] = {
            bookID: bookID,
            chapter: chapter,
            verse: verse,
            reference: reference,
            verseText: verseText,
            note: ''
        };
        this.saveBookmarks();
    }

    removeBookmark(bookID, chapter, verse) {
        const key = this.getBookmarkKey(bookID, chapter, verse);
        delete this.bookmarks[key];
        this.saveBookmarks();
    }

    updateBookmarkNote(bookID, chapter, verse, note) {
        const key = this.getBookmarkKey(bookID, chapter, verse);
        if (this.bookmarks[key]) {
            this.bookmarks[key].note = note;
            this.saveBookmarks();
        }
    }

    // =========================================================================
    // KONTEXTOVÉ MENU PRE VERŠE
    // =========================================================================

    showVerseContextMenu(event, verseLine) {
        const bookID = parseInt(verseLine.dataset.book);
        const chapter = parseInt(verseLine.dataset.chapter);
        const verse = parseInt(verseLine.dataset.verse);
        
        if (!this.verseContextMenu) return;

        const hasBookmark = this.hasBookmark(bookID, chapter, verse);
        
        // Vytvoríme menu
        this.verseContextMenu.innerHTML = '';
        
        if (hasBookmark) {
            const removeItem = document.createElement('div');
            removeItem.className = 'verse-context-menu-item';
            removeItem.textContent = 'Odstrániť záložku';
            removeItem.addEventListener('click', () => {
                this.removeBookmark(bookID, chapter, verse);
                this.hideVerseContextMenu();
                this.refreshCurrentChapter();
            });
            this.verseContextMenu.appendChild(removeItem);
        } else {
            const addItem = document.createElement('div');
            addItem.className = 'verse-context-menu-item';
            addItem.textContent = 'Pridať záložku';
            addItem.addEventListener('click', () => {
                const book = this.bibleData[bookID];
                const reference = `${book.name_sk} ${chapter},${verse}`;
                const verseText = this.cleanText(verseLine.textContent.replace(/^\d+\./, '').replace(/[*#]/g, '').trim());
                this.addBookmark(bookID, chapter, verse, verseText, reference);
                this.hideVerseContextMenu();
                this.refreshCurrentChapter();
            });
            this.verseContextMenu.appendChild(addItem);
        }

        // Kopírovať verš
        const copyVerseItem = document.createElement('div');
        copyVerseItem.className = 'verse-context-menu-item';
        copyVerseItem.textContent = 'Kopírovať verš';
        copyVerseItem.addEventListener('click', () => {
            const verseText = this.cleanText(verseLine.textContent.replace(/^\d+\./, '').replace(/[*#]/g, '').trim());
            navigator.clipboard.writeText(verseText);
            this.hideVerseContextMenu();
        });
        this.verseContextMenu.appendChild(copyVerseItem);

        // Kopírovať verš s referenciou
        const copyWithRefItem = document.createElement('div');
        copyWithRefItem.className = 'verse-context-menu-item';
        copyWithRefItem.textContent = 'Kopírovať s referenciou';
        copyWithRefItem.addEventListener('click', () => {
            const book = this.bibleData[bookID];
            const reference = `${book.name_sk} ${chapter},${verse}`;
            const verseText = this.cleanText(verseLine.textContent.replace(/^\d+\./, '').replace(/[*#]/g, '').trim());
            navigator.clipboard.writeText(`${verseText}\n(${reference})`);
            this.hideVerseContextMenu();
        });
        this.verseContextMenu.appendChild(copyWithRefItem);

        // Pozícia menu
        this.verseContextMenu.style.left = `${event.pageX}px`;
        this.verseContextMenu.style.top = `${event.pageY}px`;
        this.verseContextMenu.classList.add('active');
    }

    hideVerseContextMenu() {
        if (this.verseContextMenu) {
            this.verseContextMenu.classList.remove('active');
        }
    }

    refreshCurrentChapter() {
        if (this.currentBookID && this.currentChapter && this.currentChapter !== 0) {
            this.loadChapterContent(this.currentBookID, this.currentChapter);
        }
    }

    // =========================================================================
    // SPRÁVA ZÁLOŽIEK - MODÁLNE OKNO
    // =========================================================================

    openBookmarksModal() {
        if (!this.bookmarksModal) return;
        
        this.renderBookmarksList();
        this.bookmarksModal.classList.add('active');
    }

    closeBookmarksModal() {
        if (this.bookmarksModal) {
            this.bookmarksModal.classList.remove('active');
        }
    }

    renderBookmarksList() {
        const content = document.getElementById('bookmarksContent');
        if (!content) return;

        const bookmarkKeys = Object.keys(this.bookmarks);
        
        if (bookmarkKeys.length === 0) {
            content.innerHTML = `
                <div class="bookmarks-empty">
                    <h3>Zatiaľ nemáte žiadne záložky</h3>
                    <p>Kliknite pravým tlačidlom na verš a vyberte "Pridať záložku"</p>
                </div>
            `;
            return;
        }

        // Zoradíme záložky podľa ID knihy, kapitoly a verša
        const sortedKeys = bookmarkKeys.sort((a, b) => {
            const [bookA, chapterA, verseA] = a.split(':').map(Number);
            const [bookB, chapterB, verseB] = b.split(':').map(Number);
            
            if (bookA !== bookB) return bookA - bookB;
            if (chapterA !== chapterB) return chapterA - chapterB;
            return verseA - verseB;
        });

        let html = '<div class="bookmarks-list">';
        
        sortedKeys.forEach(key => {
            const bookmark = this.bookmarks[key];
            html += `
                <div class="bookmark-item" data-key="${key}">
                    <div class="bookmark-header">
                        <span class="bookmark-reference" data-reference="${bookmark.reference}">${bookmark.reference}</span>
                        <button class="bookmark-delete" data-key="${key}" title="Odstrániť záložku">×</button>
                    </div>
                    <div class="bookmark-verse">${bookmark.verseText}</div>
                    <div class="bookmark-note-label">Poznámka:</div>
                    <textarea 
                        class="bookmark-note" 
                        data-key="${key}"
                        placeholder="Pridajte poznámku k tomuto veršu..."
                    >${bookmark.note || ''}</textarea>
                </div>
            `;
        });
        
        html += '</div>';
        content.innerHTML = html;

        // Event listenery
        content.querySelectorAll('.bookmark-reference').forEach(el => {
            el.addEventListener('click', () => {
                const reference = el.dataset.reference;
                this.closeBookmarksModal();
                this.open(reference);
            });
        });

        content.querySelectorAll('.bookmark-delete').forEach(btn => {
            btn.addEventListener('click', () => {
                const key = btn.dataset.key;
                delete this.bookmarks[key];
                this.saveBookmarks();
                this.renderBookmarksList();
                this.refreshCurrentChapter();
            });
        });

        content.querySelectorAll('.bookmark-note').forEach(textarea => {
            textarea.addEventListener('blur', () => {
                const key = textarea.dataset.key;
                const [bookID, chapter, verse] = key.split(':').map(Number);
                
                // 1. Uložíme poznámku (toto už máte)
                this.updateBookmarkNote(bookID, chapter, verse, textarea.value);

                // 2. [NOVÉ] Skontrolujeme, či je táto záložka v aktuálne zobrazenej kapitole
                if (bookID === this.currentBookID && chapter === this.currentChapter) {
                    // Ak áno, obnovíme obsah kapitoly, aby sa aktualizoval tooltip
                    this.refreshCurrentChapter();
                }
            });
        });
    }

    exportBookmarks() {
        const dataStr = JSON.stringify(this.bookmarks, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'bible-bookmarks.json';
        link.click();
        URL.revokeObjectURL(url);
    }

    importBookmarks(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const imported = JSON.parse(e.target.result);
                // Zlúčime s existujúcimi záložkami
                this.bookmarks = { ...this.bookmarks, ...imported };
                this.saveBookmarks();
                this.renderBookmarksList();
                this.refreshCurrentChapter();
                alert('Záložky boli úspešne importované!');
            } catch (error) {
                alert('Chyba pri importe záložiek. Skontrolujte súbor.');
                console.error('Import error:', error);
            }
        };
        reader.readAsText(file);
    }

    // =========================================================================
    // [NOVÉ METÓDY] SPRÁVA HISTÓRIE
    // =========================================================================

    /**
     * Pridá nový stav do zásobníka histórie.
     * Ak sme v histórii "späť" a vykonáme novú akciu, "budúca" história sa vymaže.
     */
    addHistoryState(state) {
        // Ak práve navigujeme (klikli sme Späť/Vpred), nepridávame nový záznam
        if (this.isNavigatingHistory) return;

        // Ak sme v histórii pozadu, orežeme "budúcnosť"
        if (this.historyIndex < this.navigationHistory.length - 1) {
            this.navigationHistory = this.navigationHistory.slice(0, this.historyIndex + 1);
        }

        this.navigationHistory.push(state);
        this.historyIndex = this.navigationHistory.length - 1;

        this.updateHistoryButtons();
    }

    /**
     * Aktualizuje stav (disabled/enabled) tlačidiel Späť/Vpred.
     */
    updateHistoryButtons() {
        if (this.historyBackBtn) {
            this.historyBackBtn.disabled = this.historyIndex <= 0;
        }
        if (this.historyFwdBtn) {
            this.historyFwdBtn.disabled = this.historyIndex >= this.navigationHistory.length - 1;
        }
    }

    /**
     * Naviguje v histórii o `direction` (-1 pre späť, 1 pre vpred).
     */
    navigateHistory(direction) {
        const newIndex = this.historyIndex + direction;

        if (newIndex < 0 || newIndex >= this.navigationHistory.length) {
            return; // Mimo rozsahu
        }

        this.isNavigatingHistory = true; // Nastavíme príznak
        this.historyIndex = newIndex;
        
        const state = this.navigationHistory[this.historyIndex];
        
        // Obnovíme stav
        if (state.type === 'content') {
            this.restoreContentState(state);
        } else if (state.type === 'search') {
            this.restoreSearchState(state);
        }

        this.updateHistoryButtons();
        
        // Po krátkom čase odznačíme príznak
        setTimeout(() => {
            this.isNavigatingHistory = false;
        }, 50);
    }

    /**
     * Obnoví zobrazenie kapitoly/úvodu zo stavu histórie.
     */
    restoreContentState(state) {
        const { bookID, chapter, verseToHighlight } = state;
        
        this.currentBookID = bookID;
        this.bookSelect.value = bookID;
        this.populateChapterSelect(bookID);
        
        if (chapter === null) {
            // Stav, kedy bola vybratá len kniha (napr. chyba)
            this.mainContent.innerHTML = '<div class="bible-loading">Vyberte kapitolu...</div>';
            this.updateHeaderTitle(this.bibleData[bookID]?.name_sk || 'Kniha');
            this.chapterSelect.value = '';
            this.currentChapter = null;
            this.updateNavButtons(bookID, null);
        } else if (chapter === 0) {
            this.loadBookIntro(bookID);
        } else {
            // Pri obnovení stavu musíme poslať aj verš na zvýraznenie
            this.loadChapterContent(bookID, chapter, verseToHighlight);
        }
        
        if (chapter !== null) {
            this.chapterSelect.value = chapter;
        }
    }

    /**
     * Obnoví zobrazenie výsledkov vyhľadávania zo stavu histórie.
     */
    restoreSearchState(state) {
        const { query, results, scope } = state;
        this.searchInput.value = query;
        this.searchScopeSelect.value = scope;
        // Znovu zobrazíme uložené výsledky bez nového hľadania
        this.displaySearchResults(results, query, scope); 
    }


    // =========================================================================
    // UTILITY: ČISTENIE A NORMALIZÁCIA
    // =========================================================================
    
    normalize(name) {
        if (!name) return '';
        let normalized = name.toLowerCase()
                             .replace(/[\s\.]/g, '')
                             .normalize("NFD")
                             .replace(/[\u0300-\u036f]/g, "");
        return normalized;
    }
    
    cleanText(text) {
        if (!text) return '';
        let cleaned = text.replace(/[\u200B-\u200D\u2028-\u202E\uFEFF\u25A1\u25A0\u2020\u2021]/g, '');
        cleaned = cleaned.replace(/&[a-z]+;|&#\d+;/g, '');
        cleaned = cleaned.replace(/\[\w+\]|\[\w+\s\d+\]/g, ''); 
        cleaned = cleaned.replace(/<a[^>]*>(.*?)<\/a>/g, '$1').replace(/<\/?\w+[^>]*>/g, '');
        return cleaned.trim();
    }

    // =========================================================================
    // VYHĽADÁVANIE
    // =========================================================================
    
    getTestamentBookIDs(scope) {
        if (!this.bibleData) return [];
        const allBookIDs = Object.keys(this.bibleData).map(Number).sort((a, b) => a - b);
        const OT_SPLIT_ID = 466; 
        switch (scope) {
            case 'current': return this.currentBookID ? [this.currentBookID] : [];
            case 'ot': return allBookIDs.filter(id => id <= OT_SPLIT_ID);
            case 'nt': return allBookIDs.filter(id => id > OT_SPLIT_ID);
            case 'all': default: return allBookIDs;
        }
    }
    
    async performSearch() {
        if (!this.bibleData) return;
        const query = this.searchInput.value.trim();
        const scope = this.searchScopeSelect.value;
        
        if (query.length < 3) {
            this.mainContent.innerHTML = '<div class="bible-loading">Zadajte aspoň 3 znaky pre vyhľadávanie.</div>';
            return;
        }
        
        this.mainContent.innerHTML = '<div class="bible-loading">Vyhľadávam...</div>';
        
        const targetBookIDs = this.getTestamentBookIDs(scope);
        const normalizedQuery = this.normalize(query); 
        const results = [];
        
        for (const bookID of targetBookIDs) {
            const book = this.bibleData[bookID];
            if (!book || !book.chapters) continue;
            
            for (const chapter in book.chapters) {
                const chapterData = book.chapters[chapter];
                for (const verse of chapterData) {
                    if (verse.v > 0) {
                        const normalizedText = this.normalize(this.cleanText(verse.text)); 
                        if (normalizedText.includes(normalizedQuery)) {
                            results.push({
                                bookID: bookID,
                                bookName: book.name_sk,
                                chapter: parseInt(chapter),
                                verse: verse.v,
                                snippet: verse.text
                            });
                        }
                    }
                }
            }
        }
        
        // [UPRAVENÉ] Posielame 'scope' pre uloženie do histórie
        this.displaySearchResults(results, query, scope);
    }
    
    // [UPRAVENÉ] Pridaný parameter 'scope'
    displaySearchResults(results, query, scope = 'all') {
        
        // [NOVÉ] Pridanie stavu vyhľadávania do histórie
        if (!this.isNavigatingHistory) {
            this.addHistoryState({
                type: 'search',
                query: query,
                scope: scope,
                results: results // Uložíme výsledky pre rýchle obnovenie
            });
        }
        
        let html = `<h2>Výsledky vyhľadávania</h2>`;
        html += `<p class="search-summary">Pre <strong>"${query}"</strong> nájdených veršov: <strong>${results.length}</strong></p>`;
        
        if (results.length === 0) {
            html += '<p>Žiadne výsledky neboli nájdené v zvolenom rozsahu.</p>';
        } else {
            html += '<div class="search-results-list">';
            results.forEach(result => {
                const reference = `${result.bookName} ${result.chapter},${result.verse}`;
                html += `<div class="search-result-item" data-ref="${reference}">`;
                html += `   <p class="result-reference">${result.bookName} ${result.chapter},${result.verse}</p>`;
                html += `   <p class="result-snippet">${this.cleanText(result.snippet)}</p>`; 
                html += `</div>`;
            });
            html += '</div>';
        }
        
        this.mainContent.innerHTML = html;
        this.scrollToTop();
        
        document.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const ref = item.dataset.ref;
                this.open(ref); 
            });
        });
    }

    // =========================================================================
    // SPRACOVANIE BIBLICKÝCH ODKAZOV
    // =========================================================================
    
    addVerseLinkListeners() {
        const verseLinks = this.mainContent.querySelectorAll('a[href^="b:"], a[href^="B:"]');
        console.log('Počet nájdených odkazov:', verseLinks.length);
        
        verseLinks.forEach(link => {
            const href = link.getAttribute('href');
            link.style.cursor = 'pointer';
            link.style.color = '#3584e4';
            link.style.textDecoration = 'underline';
            const newLink = link.cloneNode(true);
            link.parentNode.replaceChild(newLink, link);
            
            newLink.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const hrefValue = newLink.getAttribute('href');
                console.log('Kliknuté na odkaz:', hrefValue);
                this.handleVerseLink(hrefValue);
            });
        });
    }

    handleVerseLink(href) {
        console.log('handleVerseLink volaná s:', href);
        const match = href.match(/[bB]:(\d+)(?:\s+(\d+)(?::(\d+))?)?/);
        if (!match) {
            console.warn('Neplatný formát odkazu:', href);
            return;
        }
        
        const bookID = parseInt(match[1]);
        const chapter = match[2] ? parseInt(match[2]) : null;
        const verse = match[3] ? parseInt(match[3]) : null;
        
        console.log(`Navigácia na: Kniha ${bookID}, Kapitola ${chapter || 'N/A'}, Verš ${verse || 'N/A'}`);

        const bookName = this.bibleData?.[bookID]?.name_sk || '';
        if (!bookName) {
            console.warn(`Nepodarilo sa nájsť meno knihy pre ID ${bookID}.`);
            return;
        }

        let referenceString = bookName;
        if (chapter) {
            referenceString += ` ${chapter}`;
            if (verse) {
                referenceString += `,${verse}`; 
            }
        }
        
        console.log(`Volám open() s referenciou: "${referenceString}"`);
        // Volanie open() pridá nový záznam do histórie
        this.open(referenceString);
    }
    
    // [UPRAVENÉ] Táto metóda sa už priamo nevolá na zvýraznenie, ale nechávame ju pre prípadné budúce použitie
    navigateToVerse(bookID, chapter, verse) {
        this.currentBookID = bookID;
        this.bookSelect.value = bookID;
        this.populateChapterSelect(bookID);
        
        this.currentChapter = chapter;
        this.chapterSelect.value = chapter;
        
        // [ZMENA] Už len voláme loadChapterContent s veršom
        this.loadChapterContent(bookID, chapter, verse);
    }

    parseReference(reference) {
        if (!this.bibleData) return null;
        const parts = reference.match(/^(.+?)(?:\s+(\d+)(?:,(\d+))?)?$/); 
        if (!parts) return null;
        
        const bookPart = parts[1].trim();
        const chapter = parts[2] ? parseInt(parts[2]) : null;
        const verse = parts[3] ? parseInt(parts[3]) : null;
        
        let bookID = null;
        const normalizedSearch = this.normalize(bookPart); 

        for (const id in this.bibleData) {
            const book = this.bibleData[id];
            const normalizedLongName = this.normalize(book.name_sk);
            const normalizedShortName = this.normalize(book.short_name);

            if (normalizedLongName.includes(normalizedSearch) || normalizedShortName.includes(normalizedSearch)) {
                bookID = id;
                break;
            }
        }

        if (!bookID) return null;
        return { book: parseInt(bookID), chapter: chapter, verse: verse };
    }
    
    open(reference) {
         if (!this.bibleData) {
            this.mainContent.innerHTML = '<div class="bible-loading">Dáta Biblie sa ešte načítavajú. Skúste znova o chvíľu.</div>';
            this.modal.classList.add('active');
            return;
        }

        const ref = this.parseReference(reference);
        this.modal.classList.add('active');

        if (ref && ref.book) {
            this.currentBookID = ref.book;
            this.bookSelect.value = this.currentBookID;
            this.populateChapterSelect(this.currentBookID);

            if (ref.chapter) {
                this.currentChapter = ref.chapter;
                this.chapterSelect.value = this.currentChapter;
                
                if (ref.chapter === 0) {
                     this.loadBookIntro(this.currentBookID);
                } else {
                    // [UPRAVENÉ] Posielame ref.verse do loadChapterContent
                    // Logika zvýraznenia sa presunula tam
                    this.loadChapterContent(this.currentBookID, this.currentChapter, ref.verse);
                }
            } else {
                 this.loadBookIntro(this.currentBookID);
            }
        } else {
             this.mainContent.innerHTML = `<div class="error-message">Nepodarilo sa nájsť odkaz pre referenciu: ${reference}.</div>`;
        }
    }
    
    close() {
        this.modal.classList.remove('active');

        // [NOVÉ] Vyčistenie histórie pri zatvorení modálneho okna
        this.navigationHistory = [];
        this.historyIndex = -1;
        this.isNavigatingHistory = false;
        this.updateHistoryButtons(); // Vynuluje tlačidlá
        
        // Skryť aj kontextové menu
        this.hideVerseContextMenu();
    }

    scrollToTop() {
        // 'this.mainContent' je už definované v konštruktore 
        // ako document.getElementById('bibleMainContent')
        if (this.mainContent) {
            this.mainContent.scrollTop = 0;
        }
    }

    updateNavButtons(bookID, currentChapter) {
        const book = this.bibleData[bookID];
        if (!book || !book.chapters) {
            this.prevBtn.disabled = true;
            this.nextBtn.disabled = true;
            return;
        }

        const chapters = Object.keys(book.chapters).map(Number).sort((a, b) => a - b);
        const hasIntro = !!book.intro_html;
        
        if (currentChapter === null) { 
            this.prevBtn.disabled = true;
            this.nextBtn.disabled = chapters.length === 0 ? true : false;
            return;
        }
        
        if (currentChapter === 0) {
            this.prevBtn.disabled = true;
            this.nextBtn.disabled = chapters.length === 0;
            return;
        }

        const currentIndex = chapters.indexOf(currentChapter);
        this.prevBtn.disabled = !hasIntro && currentIndex === 0;
        this.nextBtn.disabled = currentIndex >= chapters.length - 1;
    }

    navigateChapter(direction) {
        if (!this.currentBookID || !this.bibleData) return;

        const book = this.bibleData[this.currentBookID];
        const chapters = Object.keys(book.chapters).map(Number).sort((a, b) => a - b);
        const hasIntro = !!book.intro_html;

        if (this.currentChapter === 0 && direction === 1) {
            if (chapters.length > 0) {
                this.loadChapterContent(this.currentBookID, chapters[0]);
            }
            return;
        }
        
        if (this.currentChapter === chapters[0] && direction === -1 && hasIntro) {
            this.loadBookIntro(this.currentBookID);
            return;
        }

        let currentIndex = chapters.indexOf(this.currentChapter);
        let newIndex = currentIndex + direction;
        
        if (newIndex >= 0 && newIndex < chapters.length) {
            const newChapter = chapters[newIndex];
            this.chapterSelect.value = newChapter;
            this.loadChapterContent(this.currentBookID, newChapter);
        }
    }

    addCommentaryToggleListeners() {
        document.querySelectorAll('.commentary-icon').forEach(icon => {
            icon.addEventListener('click', (e) => {
                const verse = e.target.dataset.verseToggle;
                this.toggleCommentary(verse);
            });
        });
    }

    toggleCommentary(verse) {
        const bookID = this.currentBookID;
        const chapter = this.currentChapter;
        const commentaryElement = document.getElementById(`commentary-${verse}`);
        if (!commentaryElement) return;

        if (commentaryElement.style.display === 'block') {
            commentaryElement.style.display = 'none';
        } else {
            const commentary = this.commentaryData?.[bookID]?.[chapter]?.[verse];
            if (commentary && commentary.text) {
                let content = `<h4>Komentár k veršu ${verse}</h4>`;
                content += `<div class="commentary-text">${commentary.text}</div>`;
                commentaryElement.innerHTML = content;
                commentaryElement.style.display = 'block';
                this.addVerseLinkListeners();
            }
        }
    }

    // =========================================================================
    // OSTATNÉ METÓDY
    // =========================================================================

    async initData() {
        this.mainContent.innerHTML = '<div class="bible-loading">Načítavam dáta Biblie...</div>';
        
        // Načítame záložky
        this.loadBookmarks();
        
        try {
            const bibleResponse = await fetch("bible_data.json");
            this.bibleData = await bibleResponse.json();
            
            try {
                const commentaryResponse = await fetch("commentary_data.json");
                this.commentaryData = await commentaryResponse.json();
                console.log("Komentáre úspešne načítané.");
            } catch (err) {
                console.warn("commentary_data.json nebol nájdený alebo platný. Komentáre nebudú dostupné.");
            }
            
            this.populateBookSelect(this.bibleData);
            this.mainContent.innerHTML = '<div class="bible-loading">Dáta úspešne načítané. Vyberte knihu alebo kliknite na referenciu.</div>';

            // [NOVÉ] Inicializácia stavu tlačidiel histórie
            this.updateHistoryButtons();

        } catch (error) {
            console.error("Kritická chyba pri načítaní BIBLICKÝCH dát:", error);
            this.mainContent.innerHTML = `<div class="error-message">Chyba pri načítaní dát (bible_data.json): ${error.message}. Skontrolujte súbor.</div>`;
        }
    }
    
    populateBookSelect(data) {
        this.bookSelect.innerHTML = '<option value="">Vyberte knihu...</option>';
        const sortedBookIDs = Object.keys(data).map(Number).sort((a, b) => a - b);
        
        for (const id of sortedBookIDs) {
            const book = data[id];
            if (!book || !book.name_sk) continue; 
            
            const option = document.createElement('option');
            option.value = id; 
            option.textContent = book.name_sk;
            this.bookSelect.appendChild(option);
        }
    }
    
    populateChapterSelect(bookID) {
        this.chapterSelect.innerHTML = ''; 
        this.chapterSelect.disabled = true;
        
        const book = this.bibleData[bookID];
        if (!book || !book.chapters) return;

        const hasIntro = !!book.intro_html; 

        if (hasIntro) { 
            const introOption = document.createElement('option');
            introOption.value = '0'; 
            introOption.textContent = 'Úvod';
            this.chapterSelect.appendChild(introOption);
        } else {
             const placeholder = document.createElement('option');
             placeholder.value = "";
             placeholder.textContent = "Kapitola...";
             placeholder.disabled = true;
             placeholder.selected = true;
             this.chapterSelect.appendChild(placeholder);
        }

        const chapterIDs = Object.keys(book.chapters).map(Number).sort((a, b) => a - b);

        for (const id of chapterIDs) {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = id;
            this.chapterSelect.appendChild(option);
        }
        this.chapterSelect.disabled = chapterIDs.length === 0 && !hasIntro; 
    }
    
    handleBookChange() {
        this.currentBookID = this.bookSelect.value ? parseInt(this.bookSelect.value) : null;
        this.currentChapter = null;
        
        this.populateChapterSelect(this.currentBookID);
        
        if (this.currentBookID) {
            this.loadBookIntro(this.currentBookID); 
        } else {
            this.mainContent.innerHTML = '<div class="bible-loading">Vyberte knihu a kapitolu</div>';
        }
    }
    
    handleChapterChange() { 
        this.currentChapter = this.chapterSelect.value ? parseInt(this.chapterSelect.value) : null;
        if (!this.currentBookID) return;

        if (this.currentChapter === 0) { 
            this.loadBookIntro(this.currentBookID);
        } else if (this.currentChapter) {
            this.loadChapterContent(this.currentBookID, this.currentChapter);
        }
    }
    
    loadBookIntro(bookID) { 
        // [NOVÉ] Pridanie stavu do histórie
        if (!this.isNavigatingHistory) {
            this.addHistoryState({
                type: 'content',
                bookID: bookID,
                chapter: 0, // 0 = Úvod
                verseToHighlight: null
            });
        }
        
        const book = this.bibleData[bookID];
        const bookName = book?.name_sk || 'Kniha';

        if (!book || !book.intro_html) {
             this.mainContent.innerHTML = `<h1>${bookName}</h1><p>Pre túto knihu nie je dostupný úvod.</p>`;
             this.updateHeaderTitle(`${bookName}`);
             this.updateNavButtons(bookID, null); 
             this.currentChapter = null;
             this.chapterSelect.value = '';
             return;
        }

        this.updateHeaderTitle(`${bookName} - Úvod`);
        this.currentChapter = 0; 
        this.chapterSelect.value = '0'; 

        let html = `<div class="intro-content">${book.intro_html}</div>`;
        
        this.mainContent.innerHTML = html;
        this.updateNavButtons(bookID, 0); 
        this.scrollToTop();
        this.addVerseLinkListeners();
    }
    
    updateHeaderTitle(title) {
        const h2 = document.querySelector('#bibleModal .bible-header h2');
        if (h2) h2.textContent = title;
    }

    // [UPRAVENÉ] Pridaný parameter 'verseToHighlight'
    loadChapterContent(bookID, chapter, verseToHighlight = null) {
        
        // [NOVÉ] Pridanie stavu do histórie
        if (!this.isNavigatingHistory) {
            this.addHistoryState({
                type: 'content',
                bookID: bookID,
                chapter: chapter,
                verseToHighlight: verseToHighlight // Uložíme aj verš
            });
        }
        
        const book = this.bibleData[bookID];
        const chapterData = book?.chapters?.[chapter];
        const bookName = book?.name_sk || 'Kniha';
        
        if (!book || !chapterData) {
            this.mainContent.innerHTML = `<div class="error-message">Kapitola ${chapter} v knihe ${bookName} nebola nájdená v dátach.</div>`;
            return;
        }

        let html = '<div class="bible-chapter-content">';
        chapterData.forEach(verse => {
            if (verse.v === 0) {
                 html += verse.text; 
                 return;
            }
            const hasCommentary = this.commentaryData?.[bookID]?.[chapter]?.[verse.v]?.text;
            
            // Namiesto "hasBookmark" získame celý objekt záložky
            const bookmarkKey = this.getBookmarkKey(bookID, chapter, verse.v);
            const bookmark = this.bookmarks[bookmarkKey]; // Bude to objekt alebo 'undefined'

            html += `<p class="verse-line" data-book="${bookID}" data-chapter="${chapter}" data-verse="${verse.v}">`;
            const cleanedText = this.cleanText(verse.text);
            html += `<span class="verse-number" id="v${verse.v}">${verse.v}.</span> ${cleanedText}`;
            
            // Komentár má prednosť
            if (hasCommentary) {
                html += ` <span class="commentary-icon" data-verse-toggle="${verse.v}" title="Zobraziť komentár">*</span>`;
            }
            
            // Potom záložka
            if (bookmark) {
                // Skontrolujeme, či poznámka existuje a nie je prázdna
                const note = bookmark.note || '';
                const tooltipText = note.trim() ? note : 'Žiadna poznámka';
                
                // Ochrana pre prípad, že by poznámka obsahovala úvodzovky
                const safeTooltipText = tooltipText.replace(/"/g, '&quot;');
                
                html += ` <span class="bookmark-icon" title="${safeTooltipText}">#</span>`;
            }
            
            html += `</p>`;
            html += `<div class="commentary-content" id="commentary-${verse.v}" style="display:none;"></div>`;
        });
        html += '</div>';
        
        this.mainContent.innerHTML = html;
        this.chapterSelect.value = chapter;
        this.currentChapter = chapter;
        this.updateNavButtons(bookID, chapter);
        this.updateHeaderTitle(`${bookName} ${chapter}`);
        
        this.addCommentaryToggleListeners(); 
        this.addVerseLinkListeners();
        this.scrollToTop();

        // [NOVÉ] Logika zvýraznenia presunutá sem
        if (verseToHighlight) {
            setTimeout(() => {
                const verseElement = document.getElementById(`v${verseToHighlight}`);
                if (verseElement) {
                    const blockToHighlight = verseElement.closest('.verse-line');
                    if (blockToHighlight) {
                        blockToHighlight.scrollIntoView({ behavior: 'smooth', block: 'start' });
                        blockToHighlight.classList.add('highlighted-block');
                        setTimeout(() => {
                            blockToHighlight.classList.remove('highlighted-block');
                        }, 5000);
                    }
                }
            }, 100); 
        }
    }
}


// =========================================================================
// INICIALIZÁCIA
// =========================================================================

let bibleApp = null;

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('bibleModal')) {
        bibleApp = new BibleApp();
        
        // Event listener pre zatvorenie modálneho okna záložiek
        const closeBookmarksBtn = document.getElementById('closeBookmarksBtn');
        if (closeBookmarksBtn) {
            closeBookmarksBtn.addEventListener('click', () => bibleApp.closeBookmarksModal());
        }

        // Event listenery pre export/import záložiek
        const exportBtn = document.getElementById('exportBookmarksBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => bibleApp.exportBookmarks());
        }

        const importBtn = document.getElementById('importBookmarksBtn');
        const importFile = document.getElementById('importBookmarksFile');
        if (importBtn && importFile) {
            importBtn.addEventListener('click', () => importFile.click());
            importFile.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    bibleApp.importBookmarks(e.target.files[0]);
                    e.target.value = ''; // Reset input
                }
            });
        }
        
        const verseReference = document.getElementById('verseReference');
        if (verseReference) {
            verseReference.style.cursor = 'pointer';
            verseReference.title = 'Kliknite pre otvorenie biblickej aplikácie a verša';
            
            verseReference.addEventListener('click', (e) => {
                e.preventDefault();
                const reference = verseReference.textContent.trim();
                // Pri otvorení z hlavnej stránky sa história automaticky resetne (vďaka logike v close())
                bibleApp.open(reference);
            });
        }
    }
});