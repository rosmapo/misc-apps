package local.mapviewer;

import org.mapsforge.core.model.BoundingBox;
import org.mapsforge.core.model.Dimension;
import org.mapsforge.core.model.MapPosition;
import org.mapsforge.core.util.LatLongUtils;
import org.mapsforge.map.awt.graphics.AwtGraphicFactory;
import org.mapsforge.map.awt.view.MapView;
import org.mapsforge.map.datastore.MultiMapDataStore;
import org.mapsforge.map.layer.cache.FileSystemTileCache;
import org.mapsforge.map.layer.cache.InMemoryTileCache;
import org.mapsforge.map.layer.cache.TileCache;
import org.mapsforge.map.layer.cache.TwoLevelTileCache;
import org.mapsforge.map.layer.renderer.TileRendererLayer;
import org.mapsforge.map.reader.MapFile;
import org.mapsforge.map.rendertheme.ExternalRenderTheme;
import org.mapsforge.map.rendertheme.InternalRenderTheme;
import org.mapsforge.map.rendertheme.XmlRenderTheme;
import org.mapsforge.map.rendertheme.ZipRenderTheme;
import org.mapsforge.map.rendertheme.ZipXmlThemeResourceProvider;
import org.mapsforge.core.util.Parameters;

import javax.swing.*;
import java.io.File;
import java.io.FileInputStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.zip.ZipInputStream;

/**
 * Minimalny prehliadac Mapsforge map.
 *
 * Pouzitie:
 *   java -jar mapviewer-1.0.jar --map slovakia.map [--map dalsia.map] [--theme Elevate.zip|tema.xml]
 *
 * Ovladanie: tahanie = posun, koliesko = zoom, dvojklik = priblizit.
 *
 * Dlazdice sa ukladaju do ~/.cache/mapviewer, takze druhe a dalsie spustenia
 * (a navrat na uz videne miesta) su rychle.
 */
public final class Viewer {

    public static void main(String[] args) throws Exception {
        List<File> maps = new ArrayList<>();
        File theme = null;
        boolean persistent = false;
        int tile = 0;

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--tile":  tile = Integer.parseInt(args[++i]); break;
                case "--map":   maps.add(new File(args[++i])); break;
                case "--theme": theme = new File(args[++i]); break;
                case "--persistent-cache": persistent = true; break;
                default:
                    System.err.println("Neznamy argument: " + args[i]);
                    System.exit(2);
            }
        }
        if (maps.isEmpty()) {
            System.err.println("Pouzitie: --map subor.map [--map ...] [--theme tema.zip|tema.xml]");
            System.exit(2);
        }

        // --- vykonove nastavenia (musia byt pred vytvorenim vrstvy) ---
        // viac renderovacich vlakien (predvolene je 1)
        Parameters.NUMBER_OF_THREADS = Math.max(2, Runtime.getRuntime().availableProcessors());
        // pocas nacitavania ukaz zvacsenu dlazdicu z nizsieho zoomu namiesto prazdneho stvorca
        Parameters.PARENT_TILES_RENDERING = Parameters.ParentTilesRendering.SPEED;
        // nerenderuj zbytocne stvorcovy buffer pri obdlznikovom okne
        Parameters.SQUARE_FRAME_BUFFER = false;

        final File themeFinal = theme;
        final boolean persistentFinal = persistent;
        final int tileFinal = tile;
        SwingUtilities.invokeLater(() -> {
            try {
                show(maps, themeFinal, persistentFinal, tileFinal);
            } catch (Exception e) {
                e.printStackTrace();
                JOptionPane.showMessageDialog(null, e.toString(), "Chyba", JOptionPane.ERROR_MESSAGE);
                System.exit(1);
            }
        });
    }

    private static void show(List<File> maps, File themeFile, boolean persistentCache, int tileSize) throws Exception {
        final File posFile = positionFile(maps);
        MapView mapView = new MapView();
        mapView.getMapScaleBar().setVisible(true);
        mapView.getFpsCounter().setVisible(false);

        // vacsie dlazdice = menej dlazdic na renderovanie (mapa vsak vyzera zvacsena)
        if (tileSize > 0) {
            mapView.getModel().displayModel.setFixedTileSize(tileSize);
        }

        // pred-renderuj viac okolo viditelnej casti (menej prazdnych stvorcov pri posune)
        mapView.getModel().frameBufferModel.setOverdrawFactor(1.8);

        // --- mapove data (viac .map suborov sa spoji) ---
        MultiMapDataStore store = new MultiMapDataStore(MultiMapDataStore.DataPolicy.RETURN_ALL);
        for (File f : maps) {
            store.addMapDataStore(new MapFile(f), false, false);
        }

        // --- dvojurovnova cache: pamat + disk (pretrvava medzi spusteniami) ---
        int ts = mapView.getModel().displayModel.getTileSize();
        int memTiles = (int) Math.min(2048,
                Math.max(128, Runtime.getRuntime().maxMemory() / 4 / ((long) ts * ts * 4)));
        TileCache tileCache = new TwoLevelTileCache(
                new InMemoryTileCache(memTiles),
                new FileSystemTileCache(
                        20_000,
                        cacheDir(maps, themeFile),
                        AwtGraphicFactory.INSTANCE,
                        persistentCache));

        // --- vrstva s renderovanim ---
        TileRendererLayer layer = new TileRendererLayer(
                tileCache, store, mapView.getModel().mapViewPosition, AwtGraphicFactory.INSTANCE);
        layer.setXmlRenderTheme(loadTheme(themeFile));
        mapView.getLayerManager().getLayers().add(layer);

        mapView.getModel().mapViewPosition.setZoomLevelMin((byte) 0);
        BoundingBox bb = store.boundingBox();

        JFrame frame = new JFrame("Map viewer");
        frame.setDefaultCloseOperation(WindowConstants.EXIT_ON_CLOSE);
        frame.add(mapView);
        frame.setSize(1100, 750);
        frame.setLocationRelativeTo(null);
        frame.addWindowListener(new java.awt.event.WindowAdapter() {
            @Override
            public void windowClosing(java.awt.event.WindowEvent e) {
                savePosition(posFile, mapView);
                mapView.destroyAll();
                AwtGraphicFactory.clearResourceMemoryCache();
                store.close();
            }
        });
        frame.setVisible(true);

        // Az ked ma okno skutocnu velkost: nastav poziciu a vynut prekreslenie.
        // Bez toho zostane mapa po starte biela, kym sa nepohne mysou.
        javax.swing.Timer kick = new javax.swing.Timer(300, ev -> {
            Dimension dim = mapView.getModel().mapViewDimension.getDimension();
            if (dim == null || dim.width <= 0 || dim.height <= 0) {
                dim = new Dimension(mapView.getWidth(), mapView.getHeight());
            }
            MapPosition saved = loadPosition(posFile, bb);
            if (saved != null) {
                mapView.getModel().mapViewPosition.setMapPosition(saved);
            } else {
                byte zoom = LatLongUtils.zoomForBounds(
                        dim, bb, mapView.getModel().displayModel.getTileSize());
                mapView.getModel().mapViewPosition.setMapPosition(
                        new MapPosition(bb.getCenterPoint(), zoom));
            }
            mapView.getLayerManager().redrawLayers();
            mapView.repaint();
        });
        kick.setRepeats(false);
        kick.start();
    }

    /** Subor s poslednou poziciou; zavisi len od zoznamu map (nie od temy). */
    private static File positionFile(List<File> maps) {
        int h = 17;
        for (File f : maps) {
            h = 31 * h + f.getAbsolutePath().hashCode();
        }
        return new File(System.getProperty("user.home"),
                ".cache/mapviewer/position-" + Integer.toHexString(h) + ".properties");
    }

    private static void savePosition(File f, MapView mapView) {
        try {
            var mvp = mapView.getModel().mapViewPosition;
            var c = mvp.getCenter();
            java.util.Properties p = new java.util.Properties();
            p.setProperty("lat", Double.toString(c.latitude));
            p.setProperty("lon", Double.toString(c.longitude));
            p.setProperty("zoom", Byte.toString(mvp.getZoomLevel()));
            f.getParentFile().mkdirs();
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(f)) {
                p.store(out, null);
            }
        } catch (Exception ignored) {
            // ukladanie pozicie nie je kriticke
        }
    }

    /** Vrati ulozenu poziciu, alebo null ak neexistuje / je mimo mapy. */
    private static MapPosition loadPosition(File f, BoundingBox bb) {
        if (!f.isFile()) {
            return null;
        }
        try (java.io.FileInputStream in = new java.io.FileInputStream(f)) {
            java.util.Properties p = new java.util.Properties();
            p.load(in);
            org.mapsforge.core.model.LatLong ll = new org.mapsforge.core.model.LatLong(
                    Double.parseDouble(p.getProperty("lat")),
                    Double.parseDouble(p.getProperty("lon")));
            byte zoom = Byte.parseByte(p.getProperty("zoom"));
            return bb.contains(ll) ? new MapPosition(ll, zoom) : null;
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * Adresar cache je zavisly od mapy a temy (cesta + cas zmeny + velkost),
     * takze pri zmene temy sa nikdy nezobrazia stare dlazdice.
     */
    private static File cacheDir(List<File> maps, File theme) {
        int h = 17;
        for (File f : maps) {
            h = 31 * h + Objects.hash(f.getAbsolutePath(), f.lastModified(), f.length());
        }
        if (theme != null) {
            h = 31 * h + Objects.hash(theme.getAbsolutePath(), theme.lastModified(), theme.length());
        }
        File base = new File(System.getProperty("user.home"), ".cache/mapviewer");
        File dir = new File(base, Integer.toHexString(h));
        dir.mkdirs();
        return dir;
    }

    /** XML tema, ZIP tema (paws.cz casto dava zip) alebo vstavana predvolena. */
    private static XmlRenderTheme loadTheme(File f) throws Exception {
        if (f == null) {
            return InternalRenderTheme.DEFAULT;
        }
        String name = f.getName().toLowerCase();
        if (name.endsWith(".zip")) {
            String xmlName = findMainXmlInZip(f);
            return new ZipRenderTheme(xmlName,
                    new ZipXmlThemeResourceProvider(new ZipInputStream(new FileInputStream(f))));
        }
        return new ExternalRenderTheme(f);
    }

    private static String findMainXmlInZip(File zip) throws Exception {
        try (java.util.zip.ZipFile zf = new java.util.zip.ZipFile(zip)) {
            var entries = zf.entries();
            String candidate = null;
            while (entries.hasMoreElements()) {
                var e = entries.nextElement();
                String n = e.getName();
                if (!e.isDirectory() && n.toLowerCase().endsWith(".xml")) {
                    if (!n.contains("/")) {
                        return n;
                    }
                    if (candidate == null) {
                        candidate = n;
                    }
                }
            }
            if (candidate == null) {
                throw new IllegalArgumentException("V zip teme nie je ziadny .xml subor");
            }
            return candidate;
        }
    }

    private Viewer() {}
}
