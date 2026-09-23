let bookmarks = [];
let editingId = null;
let activeFolderPopup = null;
let activeFolderElement = null;

// Globálna referencia na kontextové menu
const contextMenu = document.getElementById('contextMenu');

// Cache pre favikony aby sa nenačítavali opakovane
const faviconCache = new Map();

// Predvolené nastavenia gridu
const defaultSettings = {
    gridColumns: 7,
    gridWidth: 90,
    gapHorizontal: 60,
    gapVertical: 20,
    bookmarkBarColor: '#1C2027',
    bookmarkBarOpacity: 100, 
    bgColor: '#1C2027',
    bgImage: null, 
    cardBorderRadius: 25,
    bookmarkTextColor: '#bababa',
    bookmarkTextOpacity: 100,
    dateTimeColor: '#bababa',
    dateTimeOpacity: 100,
    verseTextColor: '#bababa',
    verseTextOpacity: 100,
    referenceColor: '#bababa',
    referenceOpacity: 100,
    cardShape: 'square',
    showBookmarkBar: true,
    showDateTime: true,
    showVerse: true
};

// ==========================================================
// FUNKCIA NA KONVERZIU HEX + OPACITY NA RGBA
// ==========================================================

function hexToRgba(hex, opacityPercent) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const a = opacityPercent / 100;

    return `rgba(${r}, ${g}, ${b}, ${a})`;
}

// ==========================================================
// NOVÉ FUNKCIE PRE BIBLICKÝ VERŠ, NÁHODNÝ VÝBER A ODKAZ
// ==========================================================

// Pomocná funkcia na normalizáciu referencie pre biblickú aplikáciu
// Konvertuje napr. "1 Korinťanom 15,58" na "1COR15:58"

// Funkcia na náhodný výber verša zo zoznamu
function getRandomBibleVerse() {
    // Kontrola, či existuje pole bibleVersesWithText a nie je prázdne (načítané z bible-verses.js)
    if (typeof bibleVersesWithText !== 'undefined' && bibleVersesWithText.length > 0) {
        const randomIndex = Math.floor(Math.random() * bibleVersesWithText.length);
        return bibleVersesWithText[randomIndex];
    }
    // Núdzový verš, ak sa verše nenačítajú (kvôli Syntax Error v bible-verses.js)
    return {
        ref: "1 Korinťanom 15,58",
        text: "Buďte pevní, neochvejní, vždy plní horlivosti pre Pánovo dielo."
    };
}

// Funkcia na zobrazenie náhodného verša
function displayBibleVerse() {
    const verse = getRandomBibleVerse();
    const verseTextElement = document.getElementById('verseText');
    const verseRefElement = document.getElementById('verseReference');

    if (verseTextElement && verseRefElement) {
        verseTextElement.textContent = `"${verse.text}"`;
        verseRefElement.textContent = verse.ref;
        // Nastavíme aj data atribút, ak by ho miniaplikácia používala
        verseRefElement.setAttribute('data-reference', verse.ref); 
    }
}

// Funkcia na nastavenie kliknutia na referenciu (len na referenciu, nie celý box)
function setupVerseReferenceClick() {
    const verseRefElement = document.getElementById('verseReference');

    if (verseRefElement) {
        verseRefElement.style.cursor = 'pointer';

        verseRefElement.addEventListener('click', () => {
            const reference = verseRefElement.textContent.trim();

            if (reference) {
                if (typeof bibleApp !== 'undefined' && bibleApp) {
                    bibleApp.open(reference);
                } else {
                    console.warn(`Bible app nie je načítaná.`);
                    const bibleAppModal = document.getElementById('bibleAppModal');
                    if (bibleAppModal) {
                        bibleAppModal.classList.add('active');
                    }
                }
            }
        });
    }
}


// ==========================================================
// GLOBÁLNE PREMENNÉ PRE DRAG-AND-DROP
// ==========================================================
let sortableInstance = null;
let isEditingMode = false;

// ==========================================================
// FUNKCIE PRE DRAG-AND-DROP A PORADIE
// ==========================================================

function updateBookmarkOrder(oldIndex, newIndex) {
    if (oldIndex === newIndex) return;

    const [movedItem] = bookmarks.splice(oldIndex, 1);
    bookmarks.splice(newIndex, 0, movedItem);

    chrome.storage.local.set({ bookmarks: bookmarks }, () => {
        console.log(`Nové poradie záložiek uložené: ${oldIndex} -> ${newIndex}.`);
    });
}

function initializeSortableGrid() {
    const grid = document.getElementById('grid');
    if (!grid || typeof Sortable === 'undefined') return;

    if (!sortableInstance) {
        sortableInstance = Sortable.create(grid, {
            animation: 150,
            ghostClass: 'sortable-ghost',
            filter: '.context-menu',
            preventOnFilter: false,
            disabled: !isEditingMode,

            onEnd: function (evt) {
                updateBookmarkOrder(evt.oldIndex, evt.newIndex);
            },
        });
    }
}

function setDragAndDropMode(enable) {
    isEditingMode = enable;

    if (!sortableInstance) {
        initializeSortableGrid();
    }

    if (sortableInstance) {
        sortableInstance.option('disabled', !isEditingMode);

        const grid = document.getElementById('grid');

        if (grid) {
            if (isEditingMode) {
                grid.classList.add('editing-active');
            } else {
                grid.classList.remove('editing-active');
            }
        }
    }

    closeContextMenu();
}

// ==========================================================
// PÔVODNÉ FUNKCIE PRE NASTAVENIA
// ==========================================================

function loadGridSettings() {
    chrome.storage.local.get(['gridSettings'], (result) => {
        const settings = { ...defaultSettings, ...result.gridSettings };
        applyGridSettings(settings);
        updateSettingsInputs(settings);
    });
}

function applyGridSettings(settings) {
    document.getElementById('b').style.display = settings.showBookmarkBar ? 'flex' : 'none';
    const dateTimeElement = document.getElementById('dateTime');
    if(dateTimeElement) dateTimeElement.style.display = settings.showDateTime ? 'block' : 'none';
    const verseElement = document.getElementById('bibleVerse');
    if(verseElement) verseElement.style.display = settings.showVerse ? 'flex' : 'none';

    const grid = document.getElementById('grid');
    grid.style.setProperty('--grid-columns', settings.gridColumns);
    grid.style.setProperty('--grid-width', `${settings.gridWidth}%`);
    grid.style.setProperty('--gap-horizontal', `${settings.gapHorizontal}px`);
    grid.style.setProperty('--gap-vertical', `${settings.gapVertical}px`);

    const bookmarkBarRgba = hexToRgba(settings.bookmarkBarColor, settings.bookmarkBarOpacity);
    document.body.style.setProperty('--bookmark-bar-color', bookmarkBarRgba);
    
    document.body.style.setProperty('--bg-color', settings.bgColor);

    if (settings.bgImage) {
        document.body.style.backgroundImage = `url(${settings.bgImage})`;
        document.body.style.backgroundSize = 'cover';
        document.body.style.backgroundPosition = 'center';
        document.body.style.backgroundAttachment = 'fixed';
    } else {
        document.body.style.backgroundImage = 'none';
    }

    document.documentElement.style.setProperty('--card-border-radius', `${settings.cardBorderRadius}px`);

    const bookmarkTextRgba = hexToRgba(settings.bookmarkTextColor, settings.bookmarkTextOpacity);
    document.documentElement.style.setProperty('--bookmark-text-color', bookmarkTextRgba);

    const dateTimeRgba = hexToRgba(settings.dateTimeColor, settings.dateTimeOpacity);
    document.documentElement.style.setProperty('--date-time-color', dateTimeRgba);

    const verseTextRgba = hexToRgba(settings.verseTextColor, settings.verseTextOpacity);
    document.documentElement.style.setProperty('--verse-text-color', verseTextRgba);

    const referenceRgba = hexToRgba(settings.referenceColor, settings.referenceOpacity);
    document.documentElement.style.setProperty('--reference-color', referenceRgba);

    const cardShape = settings.cardShape;
    if (cardShape === 'vivaldi') {
        grid.style.setProperty('--card-aspect-ratio', '7 / 5');
    } else {
        grid.style.setProperty('--card-aspect-ratio', '1 / 1');
    }
    document.body.dataset.cardShape = cardShape;
}

function updateSettingsInputs(settings) {
    document.getElementById('gridColumns').value = settings.gridColumns;
    document.getElementById('gridWidth').value = settings.gridWidth;
    document.getElementById('gapHorizontal').value = settings.gapHorizontal;
    document.getElementById('gapVertical').value = settings.gapVertical;

    const colorPairs = [
        'bookmarkBarColor', 'bgColor', 'bookmarkTextColor', 
        'dateTimeColor', 'verseTextColor', 'referenceColor'
    ];
    colorPairs.forEach(id => {
        const colorInput = document.getElementById(id);
        const textInput = document.getElementById(id + 'Text');
        const previewButton = document.querySelector(`.color-preview-small[data-target="${id}"]`);

        if (colorInput) colorInput.value = settings[id];
        if (textInput) textInput.value = settings[id].toUpperCase();
        if (previewButton) previewButton.style.backgroundColor = settings[id];
    });

    document.getElementById('bookmarkBarOpacity').value = settings.bookmarkBarOpacity;

    document.getElementById('bookmarkTextOpacity').value = settings.bookmarkTextOpacity;
    document.getElementById('dateTimeOpacity').value = settings.dateTimeOpacity;
    document.getElementById('verseTextOpacity').value = settings.verseTextOpacity;
    document.getElementById('referenceOpacity').value = settings.referenceOpacity;
    document.getElementById('cardBorderRadius').value = settings.cardBorderRadius;

    const cardShapeSelect = document.getElementById('cardShape');
    if (cardShapeSelect) {
        cardShapeSelect.value = settings.cardShape;
    }

    document.getElementById('showBookmarkBar').checked = settings.showBookmarkBar;
    document.getElementById('showDateTime').checked = settings.showDateTime;
    document.getElementById('showVerse').checked = settings.showVerse;

    const bgImageInput = document.getElementById('bgImage');
    if (bgImageInput) {
        bgImageInput.value = ''; 
    }
    
    document.querySelectorAll('.opacity-slider').forEach(slider => {
        const opacityValueSpan = slider.closest('.color-opacity-row').querySelector('.opacity-value');
        if (opacityValueSpan) {
            opacityValueSpan.textContent = slider.value + '%';
        }
    });
}

function saveGridSettings() {
    chrome.storage.local.get(['gridSettings'], (result) => {
        const currentSettings = { ...defaultSettings, ...result.gridSettings };

        const settings = {
            gridColumns: parseInt(document.getElementById('gridColumns').value),
            gridWidth: parseInt(document.getElementById('gridWidth').value),
            gapHorizontal: parseInt(document.getElementById('gapHorizontal').value),
            gapVertical: parseInt(document.getElementById('gapVertical').value),

            bookmarkBarColor: document.getElementById('bookmarkBarColor').value,
            bookmarkBarOpacity: parseInt(document.getElementById('bookmarkBarOpacity').value), 
            bgColor: document.getElementById('bgColor').value,

            bgImage: currentSettings.bgImage,

            showBookmarkBar: document.getElementById('showBookmarkBar').checked,
            showDateTime: document.getElementById('showDateTime').checked,
            showVerse: document.getElementById('showVerse').checked,

            cardBorderRadius: parseInt(document.getElementById('cardBorderRadius').value),

            bookmarkTextColor: document.getElementById('bookmarkTextColor').value,
            bookmarkTextOpacity: parseInt(document.getElementById('bookmarkTextOpacity').value),

            dateTimeColor: document.getElementById('dateTimeColor').value,
            dateTimeOpacity: parseInt(document.getElementById('dateTimeOpacity').value),

            verseTextColor: document.getElementById('verseTextColor').value,
            verseTextOpacity: parseInt(document.getElementById('verseTextOpacity').value),

            referenceColor: document.getElementById('referenceColor').value,
            referenceOpacity: parseInt(document.getElementById('referenceOpacity').value),

            cardShape: document.getElementById('cardShape').value
        };

        chrome.storage.local.set({ gridSettings: settings }, () => {
            applyGridSettings(settings);
        });
    });
}

function resetGridSettings() {
    chrome.storage.local.set({ gridSettings: defaultSettings }, () => {
        applyGridSettings(defaultSettings);
        updateSettingsInputs(defaultSettings);
    });
}

function handleBgImageChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const imageData = e.target.result;
        
        const newSettings = {
            gridColumns: parseInt(document.getElementById('gridColumns').value),
            gridWidth: parseInt(document.getElementById('gridWidth').value),
            gapHorizontal: parseInt(document.getElementById('gapHorizontal').value),
            gapVertical: parseInt(document.getElementById('gapVertical').value),
            bookmarkBarColor: document.getElementById('bookmarkBarColor').value,
            bookmarkBarOpacity: parseInt(document.getElementById('bookmarkBarOpacity').value),
            bgColor: document.getElementById('bgColor').value,
            
            bgImage: imageData,
            
            showBookmarkBar: document.getElementById('showBookmarkBar').checked,
            showDateTime: document.getElementById('showDateTime').checked,
            showVerse: document.getElementById('showVerse').checked,

            cardBorderRadius: parseInt(document.getElementById('cardBorderRadius').value),
            bookmarkTextColor: document.getElementById('bookmarkTextColor').value,
            bookmarkTextOpacity: parseInt(document.getElementById('bookmarkTextOpacity').value),
            dateTimeColor: document.getElementById('dateTimeColor').value,
            dateTimeOpacity: parseInt(document.getElementById('dateTimeOpacity').value),
            verseTextColor: document.getElementById('verseTextColor').value,
            verseTextOpacity: parseInt(document.getElementById('verseTextOpacity').value),
            referenceColor: document.getElementById('referenceColor').value,
            referenceOpacity: parseInt(document.getElementById('referenceOpacity').value),
            cardShape: document.getElementById('cardShape').value
        };

        chrome.storage.local.set({ gridSettings: newSettings }, () => {
            applyGridSettings(newSettings);
        });
    };
    reader.readAsDataURL(file);
}

function clearBgImage() {
     const newSettings = {
        gridColumns: parseInt(document.getElementById('gridColumns').value),
        gridWidth: parseInt(document.getElementById('gridWidth').value),
        gapHorizontal: parseInt(document.getElementById('gapHorizontal').value),
        gapVertical: parseInt(document.getElementById('gapVertical').value),
        bookmarkBarColor: document.getElementById('bookmarkBarColor').value,
        bookmarkBarOpacity: parseInt(document.getElementById('bookmarkBarOpacity').value),
        bgColor: document.getElementById('bgColor').value,
        
        bgImage: null,
        
        showBookmarkBar: document.getElementById('showBookmarkBar').checked,
        showDateTime: document.getElementById('showDateTime').checked,
        showVerse: document.getElementById('showVerse').checked,

        cardBorderRadius: parseInt(document.getElementById('cardBorderRadius').value),
        bookmarkTextColor: document.getElementById('bookmarkTextColor').value,
        bookmarkTextOpacity: parseInt(document.getElementById('bookmarkTextOpacity').value),
        dateTimeColor: document.getElementById('dateTimeColor').value,
        dateTimeOpacity: parseInt(document.getElementById('dateTimeOpacity').value),
        verseTextColor: document.getElementById('verseTextColor').value,
        verseTextOpacity: parseInt(document.getElementById('verseTextOpacity').value),
        referenceColor: document.getElementById('referenceColor').value,
        referenceOpacity: parseInt(document.getElementById('referenceOpacity').value),
        cardShape: document.getElementById('cardShape').value
    };

    chrome.storage.local.set({ gridSettings: newSettings }, () => {
        applyGridSettings(newSettings);
        const bgImageInput = document.getElementById('bgImage');
        if (bgImageInput) {
            bgImageInput.value = '';
        }
    });
}


// ==========================================================
// ZVYŠOK PÔVODNÝCH FUNKCIÍ
// ==========================================================

function updateDateTime() {
    const now = new Date();
    const days = ['Nedeľa', 'Pondelok', 'Utorok', 'Streda', 'Štvrtok', 'Piatok', 'Sobota'];
    const months = ['január', 'február', 'marec', 'apríl', 'máj', 'jún', 'júl', 'august', 'september', 'október', 'november', 'december'];

    const dayName = days[now.getDay()];
    const day = now.getDate();
    const month = months[now.getMonth()];
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');

    const dateTimeStr = `${dayName} ${day}. ${month}, ${hours}:${minutes}`;

    const dateTimeElement = document.getElementById('dateTime');
    if (dateTimeElement) {
        dateTimeElement.textContent = dateTimeStr;
        dateTimeElement.classList.add('loaded');
    }
}

setInterval(updateDateTime, 60000);
updateDateTime();

function getFaviconUrl(url) {
    try {
        if (url.startsWith('chrome://') || url.startsWith('about:')) {
            return null;
        }

        const urlObj = new URL(url);
        const domain = urlObj.hostname;

        if (faviconCache.has(domain)) {
            return faviconCache.get(domain);
        }

        const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=16`;

        faviconCache.set(domain, faviconUrl);

        return faviconUrl;
    } catch (e) {
        return null;
    }
}

function createFaviconElement(url) {
    const faviconUrl = getFaviconUrl(url);

    if (!faviconUrl) {
        const genericIcon = document.createElement('span');
        genericIcon.textContent = '🔗';
        genericIcon.className = 'favicon-placeholder';
        return genericIcon;
    }

    const img = document.createElement('img');
    img.src = faviconUrl;
    img.width = 16;
    img.height = 16;
    img.decoding = 'async';

    img.onerror = function() {
        this.style.display = 'none';
    };

    return img;
}

function closeFolderPopup() {
    if (activeFolderPopup) {
        activeFolderPopup.remove();
        activeFolderPopup = null;
    }
    if (activeFolderElement) {
        activeFolderElement.classList.remove('active-folder');
        activeFolderElement = null;
    }
}

function openFolderPopup(folder, element) {
    closeFolderPopup();

    chrome.bookmarks.getChildren(folder.id, (children) => {
        const popup = document.createElement('div');
        popup.className = 'folder-popup active';
        popup.dataset.folderId = folder.id;

        children.forEach(child => {
            if (child.url) {
                const link = document.createElement('a');
                link.href = child.url;
                link.title = child.title || child.url;

                link.onclick = (e) => {
                    if (e.button === 0) {
                        e.preventDefault();
                        window.location.href = child.url;
                    }
                };
                link.addEventListener('mousedown', (e) => handleMiddleClick(e, child.url));

                const faviconElement = createFaviconElement(child.url);
                link.appendChild(faviconElement);

                link.appendChild(document.createTextNode(' ' + child.title));
                popup.appendChild(link);
            }
        });

        const rect = element.getBoundingClientRect();
        popup.style.left = rect.left + 'px';
        popup.style.top = (rect.bottom + 5) + 'px';

        document.body.appendChild(popup);
        activeFolderPopup = popup;
        activeFolderElement = element;
        element.classList.add('active-folder');
    });
}

function toggleFolderPopup(folder, element) {
    if (isEditingMode) return;

    const isSameFolder = activeFolderElement === element;

    closeFolderPopup();

    if (isSameFolder) {
        return;
    }

    openFolderPopup(folder, element);
}

function loadBookmarkBar() {
    const bar = document.getElementById('b');

    chrome.bookmarks.getChildren("1", (bookmarks) => {
        console.log('Loaded bookmarks:', bookmarks);
        bar.innerHTML = '';

        bookmarks.forEach(item => {
            if (item.url) {
                const link = document.createElement('a');
                link.href = item.url;
                link.title = item.title || item.url;

                link.onclick = (e) => {
                    if (e.button === 0) {
                        e.preventDefault();
                        window.location.href = item.url;
                    }
                };
                link.addEventListener('mousedown', (e) => handleMiddleClick(e, item.url));

                const faviconElement = createFaviconElement(item.url);
                link.appendChild(faviconElement);

                if (faviconElement.tagName === 'IMG' && faviconElement.src) {
                    const preloader = new Image();
                    preloader.src = faviconElement.src;
                }

                link.appendChild(document.createTextNode(' ' + item.title));
                bar.appendChild(link);
            } else {
                const folder = document.createElement('span');
                folder.className = 'f';
                folder.textContent = item.title;

                folder.dataset.folderId = item.id;

                folder.addEventListener('click', (e) => {
                    e.stopPropagation();
                    toggleFolderPopup(item, folder);
                });

                folder.addEventListener('mouseenter', (e) => {
                    if (activeFolderElement && activeFolderElement !== folder && !isEditingMode) {
                        openFolderPopup(item, folder);
                    }
                });

                bar.appendChild(folder);
            }
        });

        console.log('Bookmark bar rendered with', bar.children.length, 'items');
    });
}

document.addEventListener('click', (e) => {
    if (contextMenu && contextMenu.style.display === 'block' && !e.target.closest('#contextMenu')) {
        closeContextMenu();
    }

    const isClickInsideFolderBar = e.target.closest('#b');
    const isClickInsidePopup = e.target.closest('.folder-popup');

    if (activeFolderPopup && !isClickInsideFolderBar && !isClickInsidePopup) {
        closeFolderPopup();
    }
});

function closeContextMenu() {
    if (contextMenu) {
        contextMenu.style.display = 'none';
        contextMenu.dataset.bookmarkId = '';
    }
}

function showContextMenu(e, id) {
    if (isEditingMode) return;

    e.preventDefault();

    closeContextMenu();

    const menu = contextMenu;
    menu.dataset.bookmarkId = id;

    let x = e.clientX;
    let y = e.clientY;

    const menuWidth = menu.offsetWidth;
    const menuHeight = menu.offsetHeight;
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;

    if (x + menuWidth > windowWidth) {
        x = windowWidth - menuWidth - 5;
    }
    if (y + menuHeight > windowHeight) {
        y = windowHeight - menuHeight - 5;
    }

    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    menu.style.display = 'block';
}

if (contextMenu) {
    contextMenu.addEventListener('click', (e) => {
        const menuItem = e.target.closest('.context-menu-item');
        if (!menuItem) return;

        e.stopPropagation();

        const action = menuItem.dataset.action;
        const id = contextMenu.dataset.bookmarkId;

        if (id) {
            if (action === 'edit') {
                editBookmark(id, e);
            } else if (action === 'delete') {
                deleteBookmark(id, e);
            }
        }

        closeContextMenu();
    });

    contextMenu.addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });
}

function exportData() {
    chrome.storage.local.get(null, (items) => {
        const json = JSON.stringify(items, null, 2);
        const blob = new Blob([json], { type: 'application/json' });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `custom-bookmarks-export-${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    });
}

function importData(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!confirm('Upozornenie: Import prepíše všetky vaše existujúce vlastné záložky a nastavenia! Pokračovať?')) {
        event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const importedData = JSON.parse(e.target.result);

            if (importedData.bookmarks && importedData.gridSettings) {
                chrome.storage.local.set(importedData, () => {
                    bookmarks = importedData.bookmarks;
                    renderBookmarks();
                    loadGridSettings();
                    loadBookmarkBar();

                    alert('Import bol úspešný! Grid a nastavenia boli aktualizované.');
                });
            } else {
                alert('Chyba pri importe: Súbor neobsahuje správne štruktúrované dáta (chýbajú "bookmarks" alebo "gridSettings").');
            }
        } catch (error) {
            alert(`Chyba pri parsovaní JSON: ${error.message}`);
        }
        event.target.value = '';
    };
    reader.readAsText(file);
}

function handleMiddleClick(e, url) {
    if (e.button === 1) {
        e.preventDefault();

        if (isEditingMode) return;

        if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
            chrome.tabs.create({ url: url, active: false });
        } else {
            window.open(url, '_blank');
        }
    }
}

function openBookmark(url) {
    if (isEditingMode) return;

    window.location.href = url;
}

function openModal(id = null) {
    if (isEditingMode && id === null) return;

    editingId = id;
    const modal = document.getElementById('modal');
    const modalTitle = document.getElementById('modalTitle');
    const form = document.getElementById('bookmarkForm');

    if (id !== null) {
        modalTitle.textContent = 'Upraviť záložku';
        const bookmark = bookmarks.find(b => String(b.id) === String(id));
        if (bookmark) {
            document.getElementById('name').value = bookmark.name;
            document.getElementById('url').value = bookmark.url;
            if (bookmark.image) {
                document.getElementById('imagePreview').innerHTML = `<img src="${bookmark.image}" alt="Preview">`;
            } else {
                document.getElementById('imagePreview').innerHTML = '<span class="image-preview-text">Žiadny obrázok</span>';
            }
        }
    } else {
        modalTitle.textContent = 'Pridať záložku';
        form.reset();
        document.getElementById('imagePreview').innerHTML = '<span class="image-preview-text">Kliknite na "Vyberte súbor" pre nahratie obrázka</span>';
    }

    modal.classList.add('active');
}

function closeModal() {
    document.getElementById('modal').classList.remove('active');
    document.getElementById('bookmarkForm').reset();
    document.getElementById('imagePreview').innerHTML = '<span class="image-preview-text">Kliknite na "Vyberte súbor" pre nahratie obrázka</span>';
    editingId = null;
}

function previewImage(event) {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            document.getElementById('imagePreview').innerHTML = `<img src="${e.target.result}" alt="Preview">`;
        };
        reader.readAsDataURL(file);
    }
}

function saveBookmark(event) {
    event.preventDefault();

    const name = document.getElementById('name').value;
    const url = document.getElementById('url').value;
    const imageFile = document.getElementById('image').files[0];

    const processBookmark = (imageData) => {
        if (editingId !== null) {
            const index = bookmarks.findIndex(b => String(b.id) === String(editingId));

            if (index !== -1) {
                const existingBookmark = bookmarks[index];

                bookmarks[index] = {
                    id: String(editingId),
                    name,
                    url,
                    image: imageData !== null ? imageData : existingBookmark.image
                };
            } else {
                console.error(`Chyba: Záložka s ID ${editingId} nebola nájdená.`);
            }
        } else {
            const newBookmark = {
                id: Date.now().toString(),
                name,
                url,
                image: imageData || null
            };
            bookmarks.push(newBookmark);
        }

        chrome.storage.local.set({ bookmarks }, () => {
            renderBookmarks();
            closeModal();
        });
    };

    if (imageFile) {
        const reader = new FileReader();
        reader.onload = (e) => {
            processBookmark(e.target.result);
        };
        reader.readAsDataURL(imageFile);
    } else {
        processBookmark(null);
    }
}

function deleteBookmark(id, event) {
    if (confirm('Naozaj chcete odstrániť túto záložku?')) {
        bookmarks = bookmarks.filter(b => String(b.id) !== String(id));
        chrome.storage.local.set({ bookmarks }, () => {
            renderBookmarks();
        });
    }
}

function editBookmark(id, event) {
    openModal(id);
}

function renderBookmarks() {
    const grid = document.getElementById('grid');
    const emptyState = document.getElementById('emptyState');

    if (bookmarks.length === 0) {
        grid.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }

    grid.style.display = 'grid';
    emptyState.style.display = 'none';

    grid.innerHTML = '';

    bookmarks.forEach(bookmark => {
        const card = document.createElement('div');
        card.className = 'card';

        const bookmarkIdString = String(bookmark.id);

        card.setAttribute('data-id', bookmarkIdString);

        card.onclick = (e) => {
            if (e.button === 0) {
                openBookmark(bookmark.url);
            }
        };

        card.addEventListener('mousedown', (e) => handleMiddleClick(e, bookmark.url));

        card.oncontextmenu = (e) => showContextMenu(e, bookmarkIdString);

        card.innerHTML = `
            <div class="card-image">
                ${bookmark.image ? `<img src="${bookmark.image}" alt="${bookmark.name}">` : '📖'}
            </div>
            <div class="card-content">
                <div class="card-title">${bookmark.name}</div>
            </div>
        `;

        grid.appendChild(card);
    });

    initializeSortableGrid();
    setDragAndDropMode(isEditingMode);
}

document.addEventListener('DOMContentLoaded', () => {
    chrome.storage.local.get(['bookmarks'], (result) => {
        bookmarks = result.bookmarks || [];
        renderBookmarks();
    });
    loadBookmarkBar();
    loadGridSettings();

    // === NOVÉ: Volanie funkcií pre biblický verš a nastavenie kliknutia ===
    if (typeof displayBibleVerse === 'function') {
        displayBibleVerse();
    }
    if (typeof setupVerseReferenceClick === 'function') {
        setupVerseReferenceClick();
    }
    // =====================================================================

    const dateTime = document.getElementById('dateTime');
    if (dateTime) {
        dateTime.addEventListener('click', () => openModal());
    }

    const closeBtn = document.getElementById('closeBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }

    const cancelBtn = document.getElementById('cancelBtn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closeModal);
    }

    const bookmarkForm = document.getElementById('bookmarkForm');
    if (bookmarkForm) {
        bookmarkForm.addEventListener('submit', saveBookmark);
    }

    const imageInput = document.getElementById('image');
    if (imageInput) {
        imageInput.addEventListener('change', previewImage);
    }

    const modal = document.getElementById('modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'modal') closeModal();
        });
    }

    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const toggleEditModeBtn = document.getElementById('toggleEditModeBtn');

    if (settingsBtn && settingsModal) {
        settingsBtn.addEventListener('click', () => {
            settingsModal.classList.add('active');
        });
    }

    if (closeSettingsBtn) {
        closeSettingsBtn.addEventListener('click', () => {
            settingsModal.classList.remove('active');
        });
    }

    if (toggleEditModeBtn) {
        toggleEditModeBtn.addEventListener('click', () => {
            isEditingMode = !isEditingMode;
            setDragAndDropMode(isEditingMode);

            if (isEditingMode) {
                toggleEditModeBtn.textContent = 'Ukončiť presun';
                toggleEditModeBtn.classList.add('active');
                settingsModal.classList.remove('active');
            } else {
                toggleEditModeBtn.textContent = 'Presun dlaždíc';
                toggleEditModeBtn.classList.remove('active');
            }
        });
    }

    if (settingsModal) {
        settingsModal.addEventListener('click', (e) => {
            if (e.target.id === 'settingsModal') {
                settingsModal.classList.remove('active');
            }
        });
    }

    const resetBtn = document.getElementById('resetSettings');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetGridSettings);
    }

    ['gridColumns', 'gridWidth', 'gapHorizontal', 'gapVertical', 'cardBorderRadius', 'cardShape'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', saveGridSettings);
        }
    });

    ['showBookmarkBar', 'showDateTime', 'showVerse'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.addEventListener('change', saveGridSettings);
        }
    });

    const addNewTileBtn = document.getElementById('addNewTileBtn');
    if (addNewTileBtn) {
        addNewTileBtn.addEventListener('click', () => {
            openModal();
            settingsModal.classList.remove('active');
        });
    }

    const bgImageInput = document.getElementById('bgImage');
    if (bgImageInput) {
        bgImageInput.addEventListener('change', handleBgImageChange);
    }
    
    const clearBgImageBtn = document.getElementById('clearBgImage');
    if (clearBgImageBtn) {
        clearBgImageBtn.addEventListener('click', clearBgImage);
    }

    const colorPairs = [
        { id: 'bookmarkBarColor', opacity: 'bookmarkBarOpacity' }, 
        { id: 'bgColor', opacity: null },
        { id: 'bookmarkTextColor', opacity: 'bookmarkTextOpacity' },
        { id: 'dateTimeColor', opacity: 'dateTimeOpacity' },
        { id: 'verseTextColor', opacity: 'verseTextOpacity' },
        { id: 'referenceColor', opacity: 'referenceOpacity' }
    ];

    colorPairs.forEach(pair => {
        const colorInput = document.getElementById(pair.id); 
        const textInput = document.getElementById(pair.id + 'Text'); 
        const previewButton = document.querySelector(`.color-preview-small[data-target="${pair.id}"]`);

        if (colorInput && textInput && previewButton) {
            
            const applyColorChange = (hexValue) => {
                let cleanHex = hexValue.trim().toUpperCase();
                cleanHex = cleanHex.startsWith('#') ? cleanHex : `#${cleanHex}`;

                if (!/^#([0-9A-F]{3}){1,2}$/i.test(cleanHex)) {
                    return; 
                }
                
                colorInput.value = cleanHex;
                textInput.value = cleanHex;
                previewButton.style.backgroundColor = cleanHex;
                saveGridSettings();
            };

            previewButton.addEventListener('click', function() {
                colorInput.click();
            });

            colorInput.addEventListener('input', function() {
                applyColorChange(this.value);
            });
            
            textInput.addEventListener('input', function() {
                let hexValue = this.value.trim().toUpperCase();
                hexValue = hexValue.replace(/[^#0-9A-F]/g, '');
                
                if (hexValue.length > 7) {
                    hexValue = hexValue.substring(0, 7);
                }
                
                this.value = hexValue;

                if (hexValue.length === 4 || hexValue.length === 7 || hexValue.length === 3 || hexValue.length === 6) {
                    applyColorChange(hexValue);
                }
            });
        }
        
        const opacitySlider = pair.opacity ? document.getElementById(pair.opacity) : null;
        if (opacitySlider) {
            const updateOpacityDisplay = () => {
                const opacityValueSpan = opacitySlider.closest('.color-opacity-row').querySelector('.opacity-value');
                if (opacityValueSpan) {
                    opacityValueSpan.textContent = opacitySlider.value + '%';
                }
            };
            
            opacitySlider.addEventListener('input', () => {
                updateOpacityDisplay();
                saveGridSettings(); 
            });
            opacitySlider.addEventListener('change', saveGridSettings);
        }
    });

    const exportBtn = document.getElementById('exportDataBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', exportData);
    }

    const triggerImportBtn = document.getElementById('triggerImportBtn');
    const importFileInput = document.getElementById('importFile');

    if (triggerImportBtn && importFileInput) {
        triggerImportBtn.addEventListener('click', () => {
            importFileInput.click();
        });
        importFileInput.addEventListener('change', importData);
    }
});