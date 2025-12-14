"use client";

import useSWR from "swr";
import { useEffect, useState, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import SpriteText from "three-spritetext";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Dashboard() {
  const [query, setQuery] = useState("");
  const [tickerData, setTickerData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(() => {
    try {
      return parseInt(localStorage.getItem("pageSize") || "5");
    } catch {
      return 5;
    }
    });
  const [sortBy, setSortBy] = useState("published_at");
  const [order, setOrder] = useState("desc");

  const [articles, setArticles] = useState<any[]>([]);

  const articlesUrl = `http://127.0.0.1:8000/recent_articles?page=${page}&limit=${pageSize}&sort_by=${sortBy}&order=${order}`;

  const { data, isLoading } = useSWR(articlesUrl, fetcher, {
    refreshInterval: 30000, // Refresh every 30 sec
    revalidateOnFocus: true, // Revalidate when the window regains focus
    revalidateOnReconnect: true, // Revalidate when the browser regains network connection
  });

  useEffect(() => {
    if (!data) return;

    const records = (data.records || []).map((r: any) => ({
      ...r,
      id: Number(r.id),
    }));

    if (page === 1) {
      setArticles(records);
    } else {
      setArticles((prev) => {
        const existingIds = new Set(prev.map(r => Number(r.id)));   // normalize prev too
        const filteredNew = records.filter((r: { id: any; }) => !existingIds.has(Number(r.id)));
        return [...prev, ...filteredNew];
      });
    }
  }, [data, page]);

  const totalRecords = data?.total_records ?? null;
  const hasMore = totalRecords !== null ? articles.length < totalRecords : true;

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setOrder(prev => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setOrder("desc");
    }

    setPage(1);

    setArticles([]);
  };

  const getSortArrow = (field: string) => {
    if (sortBy !== field) return "↕";
    return order === "asc" ? "▲" : "▼";
  };

  const loadMore = () => {
    if (!hasMore) return;
    setPage((p) => p + 1);
  };

    // Search ticker and get sentiment summary
  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setErrorMsg("");
    setTickerData(null);
    try {
      const res = await fetch(`http://127.0.0.1:8000/tickers/search?q=${query}`);
      if (!res.ok) throw new Error("No results found");
      const data = await res.json();
      setTickerData(data);
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setLoading(false);
    }
  };

  const ThreeDPlot = () => {
    const mountRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
      let renderer: THREE.WebGLRenderer,
        camera: THREE.PerspectiveCamera,
        scene: THREE.Scene;
      let reqId: number | null = null;

      const raycaster = new THREE.Raycaster();
      const mouse = new THREE.Vector2();

      window.addEventListener("mousemove", (event) => {
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
      });

      const mount = mountRef.current;
      if (!mount) return; // guard if ref not attached yet

      const width = mount.clientWidth;
      const height = 500;

      scene = new THREE.Scene();
      scene.background = new THREE.Color("#fafafa");

      camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 1000);
      camera.position.set(6, 6, 10);

      renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(window.devicePixelRatio || 1);
      renderer.setSize(width, height);
      renderer.setClearColor("#fafafa", 1);
      mount.appendChild(renderer.domElement);

      // Basic lighting
      const light = new THREE.PointLight(0xffffff, 1);
      light.position.set(20, 20, 20);
      scene.add(light);

      // Axes helper (XYZ axes)
      const axesHelper = new THREE.AxesHelper(5);
      scene.add(axesHelper);

      const xLabel = new SpriteText("Price Change");
      xLabel.textHeight = 0.3;
      xLabel.color = "black";
      xLabel.position.set(6, 0, 0);
      scene.add(xLabel);

      const yLabel = new SpriteText("Sentiment");
      yLabel.textHeight = 0.3;
      yLabel.color = "black";
      yLabel.position.set(0, 6, 0);
      scene.add(yLabel);

      const zLabel = new SpriteText("Relative Volume");
      zLabel.textHeight = 0.3;
      zLabel.color = "black";
      zLabel.position.set(0, 0, 6);
      scene.add(zLabel);

      const controls = new OrbitControls(camera, renderer.domElement);
      controls.enableDamping = true;

      const tooltip = new SpriteText("", 0.4, "black");
      tooltip.visible = false;
      scene.add(tooltip);
      
      const colliders: THREE.Mesh[] = [];
      const visiblePoints: THREE.Mesh[] = [];
      
      const infoPanel = document.getElementById("infoPanel");

      fetch("http://localhost:8000/analytics/ticker-performance-3d")
        .then((res) => res.json())
        .then((json) => {

          json.data.forEach((item: any) => {
            const { pct_change, relative_volume, sentiment } = item;

            const x = pct_change * 2;
            const y = sentiment * 4;
            const z = relative_volume * 1.5;

            const geometry = new THREE.SphereGeometry(0.3, 20, 20);

            const minSize = 0.15;
            const maxSize = 0.45;

            const size = minSize + (maxSize - minSize) * relative_volume;

            const color =
              sentiment > 0.2 ? "#1DFF00" : sentiment < -0.2 ? "#FF0000" : "#FFF700";

            const material = new THREE.MeshStandardMaterial({
              color,
              emissive: color,
              emissiveIntensity: 0.4,
            });

            const point = new THREE.Mesh(geometry, material);

            point.position.set(x, y, z);
            point.scale.set(size, size, size);

            point.userData = {
              symbol: item.symbol,
              pct_change: item.pct_change,
              relative_volume: item.relative_volume,
              sentiment: item.sentiment,
            };

            const collider = new THREE.Mesh(
              new THREE.SphereGeometry(0.5, 8, 8),   // bigger hit zone
              new THREE.MeshStandardMaterial({ 
                visible: false,
                color: "#0000000c"
              })
            );

            collider.position.copy(point.position);
            collider.scale.set(size * 1.0001, size * 1.0001, size * 1.0001);

            collider.userData = {
              symbol: item.symbol,
              pct_change: item.pct_change,
              relative_volume: item.relative_volume,
              sentiment: item.sentiment,
              visible: point
            };

            colliders.push(collider);
            visiblePoints.push(point);

            scene.add(collider);
            scene.add(point);
          });
        })

        .catch((err) => {
          // handle fetch error silently here
          console.error("3D data fetch error:", err);
        });

      //raycaster.params.Mesh.threshold = 0.35;

      // Animation loop
      function animate() {
        reqId = requestAnimationFrame(animate);

        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(colliders, false);
        if (hits.length > 0) {
          const hit = hits[0].object;
          const sphere = hit.userData.visible;

          tooltip.text = hit.userData?.symbol ?? "";
          tooltip.lookAt(camera.position);
          const offset = sphere.position.clone().sub(camera.position).normalize().multiplyScalar(-0.4);
          tooltip.position.copy(sphere.position).add(offset);
          tooltip.visible = true;

          infoPanel!.style.display = "block";
          infoPanel!.innerHTML = `
              <strong>${hit.userData.symbol}</strong><br>
              Price Change: ${hit.userData.pct_change.toFixed(3)}<br>
              Sentiment: ${hit.userData.sentiment.toFixed(3)}<br>
              Relative Volume: ${hit.userData.relative_volume.toFixed(3)}
          `;

          if (sphere instanceof THREE.Mesh) {
            const mat = sphere.material as THREE.Material | THREE.MeshStandardMaterial;
            if ((mat as any)?.emissive) {
              (mat as any).emissive.set("#00FFFF");
            }
          }
        } else {
          tooltip.visible = false;
          // Safely update colors only for Mesh objects that expose a color property on their material
          visiblePoints.forEach((p) => {
            if (p instanceof THREE.Mesh) {
              const mat = p.material as THREE.Material | THREE.MeshStandardMaterial;
              if ((mat as any)?.emissive) {
                const color =
                  p.userData?.sentiment > 0.2
                    ? "#1DFF00"
                    : p.userData?.sentiment < -0.2
                    ? "#FF0000"
                    : "#FFF700";
                (mat as any).emissive.set(color);
              }
            }
          });
        }

        controls.update();
        renderer.render(scene, camera);
      }
      animate();

      // Cleanup on unmount
      return () => {
        if (reqId != null) cancelAnimationFrame(reqId);
        try {
          if (mount && renderer && mount.contains(renderer.domElement)) {
            mount.removeChild(renderer.domElement);
          }
        } catch (e) {
          // ignore remove errors
        }
        try {
          controls.dispose();
        } catch {}
        try {
          renderer.dispose();
        } catch {}
      };
    }, []);

    return (
      <div style= {{ position: "relative" }}>
        <div ref={mountRef}
          style={{
          width: "100%",
          height: "500px",
          border: "1px solid #333",
          marginTop: "20px",
        }} />
        <div id = "infoPanel"
          style={{
            position: "absolute",
            right: "20px",
            top: "20px",
            background: "white",
            padding: "12px 16px",
            borderRadius: "8px",
            boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
            fontSize: "14px",
            lineHeight: "1.4",
            display: "none",
            border: "1px solid #ccc",
            zIndex: 10  // Make sure it's above canvas
          }}
        ></div>
      </div>
    );
  };

  return (
    <main style={{ padding: "2rem", fontFamily: "sans-serif" }}>
      <h1 style={{
        fontSize: "2.5rem",
        fontWeight: 700,
        marginBottom: "1rem",
        color: "#111827",
        textAlign: "center"
      }}>
        News Sentiment Dashboard
      </h1>

      {/* --- Search Section --- */}
      <section style={{
        background: "#fff",
        borderRadius: "12px",
        padding: "1.5rem",
        boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
        marginBottom: "2rem"
      }}>

        <h2>Search Ticker</h2>
        <input
          type="text"
          placeholder="Enter ticker (e.g. NVDA)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{
            padding: "0.5rem",
            fontSize: "1rem",
            marginRight: "0.5rem",
            border: "3px solid #cccccca1",
            width: "250px",
          }}
        />
        <button
          onClick={handleSearch}
          style={{
            padding: "0.5rem 1rem",
            fontSize: "1rem",
            backgroundColor: "#0070f3",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: "pointer",
          }}
        >
          Search
        </button>

        {loading && <p>Loading...</p>}
        {errorMsg && <p style={{ color: "red" }}>{errorMsg}</p>}

        {tickerData && (
          <div style={{ marginTop: "1rem" }}>
            <h3 style={{ marginBottom: "1rem" }}>
              {tickerData.symbol} Summary
            </h3>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                marginBottom: "1rem",
              }}
            >
              <thead style={{ backgroundColor: "#f9fafb" }}>
                <tr>
                  <th style={{ padding: "8px", textAlign: "left" }}>Metric</th>
                  <th style={{ padding: "8px", textAlign: "right" }}>Value</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style={{ padding: "8px" }}>Articles</td>
                  <td style={{ padding: "8px", textAlign: "right" }}>{tickerData.summary.article_count}</td>
                </tr>
                <tr>
                  <td style={{ padding: "8px" }}>Avg Price Change (1d)</td>
                  <td style={{ padding: "8px", textAlign: "right" }}>
                    {tickerData.summary.avg_pct_change
                      ? tickerData.summary.avg_pct_change.toFixed(2) + "%"
                      : "—"}
                  </td>
                </tr>
                <tr>
                  <td style={{ padding: "8px" }}>Avg Relative Volume</td>
                  <td style={{ padding: "8px", textAlign: "right" }}>
                    {tickerData.summary.avg_relative_volume
                      ? tickerData.summary.avg_relative_volume.toFixed(2)
                      : "—"}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
        {Array.isArray(tickerData?.articles) && tickerData.articles.length > 0 && (
          <div style={{ marginTop: "1.5rem" }}>
            <h3>Article Sentiment Breakdown</h3>

            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                marginTop: "1rem",
              }}
            >
              <thead style={{ backgroundColor: "#f3f4f6" }}>
                <tr>
                  <th style={{ padding: "8px" }}>Headline</th>
                  <th style={{ padding: "8px", textAlign: "center" }}>Sentiment</th>
                  <th style={{ padding: "8px", textAlign: "center" }}>Published</th>
                </tr>
              </thead>

              <tbody>
                {tickerData.articles.map((a: any, idx: number) => {
                  const pubDate = a.published_at
                    ? new Date(a.published_at).toLocaleString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—";

                  return (
                    <tr
                      key={idx}
                      style={{
                        backgroundColor: idx % 2 === 0 ? "#fff" : "#f9fafb",
                      }}
                    >
                      <td style={{ padding: "8px" }}>
                        {a.url ? (
                          <a href={a.url} target="_blank" rel="noopener noreferrer">
                            {a.headline}
                          </a>
                        ) : (
                          a.headline
                        )}
                      </td>

                      <td
                        style={{
                          padding: "8px",
                          textAlign: "center",
                          color:
                            a.combined_score > 0
                              ? "green"
                              : a.combined_score < 0
                              ? "red"
                              : "gray",
                        }}
                      >
                        {a.combined_score?.toFixed(3)}
                      </td>

                      <td style={{ padding: "8px", textAlign: "center" }}>
                        {pubDate}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* --- Recent Articles Table --- */}
      <section
        style={{
          background: "#fff",
          borderRadius: "12px",
          padding: "1.5rem",
          boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
          marginBottom: "2rem",
        }}
      >

        <div style={{ marginBottom: "1rem", display: "flex", alignItems: "center", gap: "8px" }}>
          <label style={{ fontWeight: 600 }}>Articles per page:</label>
          <select
            value={pageSize}
            onChange={(e) => {
              const newSize = Number(e.target.value);
              setPageSize(newSize);
              localStorage.setItem("pageSize", String(newSize));
              setPage(1);
              setArticles([]);
            }}
            style={{ padding: "6px" }}
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
          </select>
        </div>

        <h2>Recent Articles</h2>

        {isLoading && <p>Loading...</p>}
        {errorMsg && <p style={{ color: "red" }}>Failed to load data.</p>}

        {articles.length > 0 && (
          <table
            style={{
              width: "100%",
              marginTop: "1rem",
              borderCollapse: "collapse",
              borderRadius: "8px",
              overflow: "hidden",
            }}
          >
            <thead style={{ backgroundColor: "#f3f4f6" }}>
            <tr>
              <th style={{ padding: "12px" }}>Ticker</th>
              <th style={{ padding: "12px" }}>Headline</th>
              <th
                style={{ padding: "12px", cursor: "pointer", textAlign: "center" }}
                onClick={() => handleSort("combined_score")}
              >
                Sentiment {getSortArrow("combined_score")}
              </th>
              <th
                style={{ padding: "12px", cursor: "pointer", textAlign: "center" }}
                onClick={() => handleSort("pct_change")}
              >
                Δ Price % {getSortArrow("pct_change")}
              </th>
              <th
                style={{ padding: "12px", cursor: "pointer", textAlign: "center" }}
                onClick={() => handleSort("relative_volume")}
              >
                Rel. Vol {getSortArrow("relative_volume")}
              </th>
              <th
                style={{ padding: "12px", cursor: "pointer", textAlign: "center" }}
                onClick={() => handleSort("published_at")}
              >
                Published {getSortArrow("published_at")}
              </th>
            </tr>
            </thead>
            <tbody>
              {articles.map((row: any, idx: number) => {
                const pubDate = row.published_at
                  ? new Date(row.published_at).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—";

                return (
                  <tr
                    key={idx}
                    style={{
                      backgroundColor: idx % 2 === 0 ? "#fff" : "#f9fafb",
                    }}
                  >
                    <td style={{ padding: "12px" }}>{row.symbol}</td>

                    <td style={{ padding: "12px" }}>
                      {row.url ? (
                        <a href={row.url} target="_blank" rel="noopener noreferrer">
                          {row.headline}
                        </a>
                      ) : (
                        row.headline
                      )}
                    </td>

                    <td
                      style={{
                        padding: "12px",
                        textAlign: "center",
                        color:
                          row.combined_score > 0
                            ? "green"
                            : row.combined_score < 0
                            ? "red"
                            : "gray",
                      }}
                    >
                      {row.combined_score?.toFixed(2)}
                    </td>

                    <td style={{ padding: "12px", textAlign: "center" }}>
                      {row.pct_change !== null && row.pct_change !== undefined
                        ? row.pct_change.toFixed(2) + "%"
                        : "—"}
                    </td>

                    <td style={{ padding: "12px", textAlign: "center" }}>
                      {row.relative_volume !== null && row.relative_volume !== undefined
                        ? Number(row.relative_volume).toFixed(2)
                        : "—"}
                    </td>

                    <td style={{ padding: "12px", textAlign: "center" }}>{pubDate}</td>
                  </tr>

                );
              })}
            </tbody>
          </table>
        )}

        <button
          onClick={loadMore}
          disabled={!hasMore || isLoading}
          style={{
            marginTop: "1rem",
            padding: "0.5rem 1rem",
            backgroundColor: hasMore ? "#10b981" : "#9ca3af",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: hasMore ? "pointer" : "not-allowed",
          }}
        >
          {isLoading ? "Loading..." : hasMore ? "Load More Articles" : "No more articles"}
        </button>
      </section>

      {/* --- 3D Plot Section --- */}
      <section style={{
        background: "#fff",
        borderRadius: "12px",
        padding: "1.5rem",
        marginBottom: "2rem"
      }}>
        <h2>3D Ticker Performance Visualization</h2>
        <ThreeDPlot />
      </section>
    </main>
  );
}
