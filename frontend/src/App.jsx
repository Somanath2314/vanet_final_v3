import React, { useState, useEffect } from "react";
import Live from './Live'

function App() {
  const [loading, setLoading] = useState(false);
  const [activeMethod, setActiveMethod] = useState(null);

  const handleRun = async (method) => {
    setLoading(true);
    setActiveMethod(method);
    
    try {
      // Step 1: Inform backend about selected method
      await fetch("http://localhost:5000/api/method", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ method }),
      });

      // Step 2: Choose args based on method
      let args = [];
      if (method === "rule") {
        args = ["--gui", "--security"];
      } else if (method === "rl") {
        args = [
          "--proximity", "250",
          "--model", "rl_module/trained_models/dqn_traffic_20251108_130019/dqn_traffic_final.zip",
          "--gui",
          "--edge",
          "--security",
          "--steps", "1000",
        ];
      }

      // Step 3: Run the simulation
      const res = await fetch("http://localhost:5000/api/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ args }),
      });

      const result = await res.json();
      console.log(result);
      alert(result.message || "Simulation started");
    } catch (error) {
      console.error("❌ Error:", error);
      alert("Failed to start simulation");
    } finally {
      setLoading(false);
      setActiveMethod(null);
    }
  };

  const styles = {
    container: {
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0f172a 100%)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: "40px 20px",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    },
    wrapper: {
      maxWidth: "900px",
      width: "100%",
    },
    header: {
      textAlign: "center",
      marginBottom: "60px",
    },
    icon: {
      width: "80px",
      height: "80px",
      background: "linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)",
      borderRadius: "20px",
      margin: "0 auto 30px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      boxShadow: "0 20px 40px rgba(59, 130, 246, 0.3)",
    },
    title: {
      fontSize: "48px",
      fontWeight: "bold",
      color: "white",
      margin: "0 0 15px 0",
      letterSpacing: "-0.5px",
    },
    subtitle: {
      fontSize: "18px",
      color: "#93c5fd",
      margin: 0,
    },
    cardsContainer: {
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
      gap: "30px",
      marginBottom: "40px",
    },
    card: {
      background: "rgba(30, 41, 59, 0.8)",
      backdropFilter: "blur(10px)",
      borderRadius: "20px",
      padding: "40px 30px",
      border: "1px solid rgba(71, 85, 105, 0.5)",
      transition: "all 0.3s ease",
      cursor: "default",
    },
    cardHover: {
      transform: "translateY(-5px)",
      boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
    },
    cardIconWrapper: {
      width: "64px",
      height: "64px",
      borderRadius: "12px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      margin: "0 auto 20px",
      transition: "all 0.3s ease",
    },
    cardTitle: {
      fontSize: "28px",
      fontWeight: "bold",
      color: "white",
      margin: "0 0 10px 0",
      textAlign: "center",
    },
    cardDescription: {
      fontSize: "14px",
      color: "#94a3b8",
      margin: "0 0 25px 0",
      textAlign: "center",
    },
    paramBox: {
      background: "rgba(15, 23, 42, 0.5)",
      borderRadius: "10px",
      padding: "15px",
      border: "1px solid rgba(71, 85, 105, 0.3)",
      marginBottom: "25px",
    },
    paramLabel: {
      fontSize: "11px",
      color: "#64748b",
      marginBottom: "10px",
    },
    paramTags: {
      display: "flex",
      flexWrap: "wrap",
      gap: "8px",
    },
    paramTag: {
      padding: "5px 10px",
      borderRadius: "6px",
      fontSize: "12px",
      fontFamily: "monospace",
    },
    button: {
      width: "100%",
      padding: "16px 24px",
      fontSize: "16px",
      fontWeight: "600",
      color: "white",
      border: "none",
      borderRadius: "12px",
      cursor: "pointer",
      transition: "all 0.2s ease",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: "10px",
    },
    buttonDisabled: {
      opacity: 0.5,
      cursor: "not-allowed",
    },
    footer: {
      textAlign: "center",
      color: "#64748b",
      fontSize: "14px",
    },
    footerHighlight: {
      color: "#3b82f6",
      fontFamily: "monospace",
    },
    spinner: {
      width: "20px",
      height: "20px",
      border: "2px solid rgba(255, 255, 255, 0.3)",
      borderTopColor: "white",
      borderRadius: "50%",
      animation: "spin 0.6s linear infinite",
    },
  };

  const [hoverCard, setHoverCard] = useState(null);

  return (
    <div style={styles.container}>
      <style>
        {`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}
      </style>
      <div style={styles.wrapper}>
        {/* Simple client-side routing: show Live when at /live or when user clicked analyze */}
        {window.location.pathname === '/live' ? (
          <Live />
        ) : (
        <>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.icon}>
            <span style={{ fontSize: "40px" }}>🚗</span>
          </div>
          <h1 style={styles.title}>VANET Simulation</h1>
          <p style={styles.subtitle}>Choose your simulation method to begin</p>
        </div>

        {/* Cards Container */}
        <div style={styles.cardsContainer}>
          {/* Rule-based Card */}
          <div
            style={{
              ...styles.card,
              ...(hoverCard === "rule" ? styles.cardHover : {}),
              borderColor: hoverCard === "rule" ? "rgba(59, 130, 246, 0.5)" : "rgba(71, 85, 105, 0.5)",
            }}
            onMouseEnter={() => setHoverCard("rule")}
            onMouseLeave={() => setHoverCard(null)}
          >
            <div
              style={{
                ...styles.cardIconWrapper,
                background: "rgba(59, 130, 246, 0.2)",
              }}
            >
              <span style={{ fontSize: "32px" }}>⚙️</span>
            </div>
            <h3 style={styles.cardTitle}>Rule-Based</h3>
            <p style={styles.cardDescription}>
              Traditional algorithm-driven traffic management
            </p>

            <div style={styles.paramBox}>
              <div style={styles.paramLabel}>Parameters:</div>
              <div style={styles.paramTags}>
                <span
                  style={{
                    ...styles.paramTag,
                    background: "rgba(59, 130, 246, 0.2)",
                    color: "#93c5fd",
                  }}
                >
                  --gui
                </span>
                <span
                  style={{
                    ...styles.paramTag,
                    background: "rgba(59, 130, 246, 0.2)",
                    color: "#93c5fd",
                  }}
                >
                  --security
                </span>
              </div>
            </div>

            <button
              onClick={() => handleRun("rule")}
              disabled={loading}
              style={{
                ...styles.button,
                background: loading && activeMethod === "rule" 
                  ? "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)"
                  : "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
                ...(loading ? styles.buttonDisabled : {}),
              }}
              onMouseOver={(e) => {
                if (!loading) {
                  e.currentTarget.style.transform = "scale(1.02)";
                  e.currentTarget.style.boxShadow = "0 10px 30px rgba(59, 130, 246, 0.4)";
                }
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = "scale(1)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              {loading && activeMethod === "rule" ? (
                <>
                  <div style={styles.spinner}></div>
                  <span>Running...</span>
                </>
              ) : (
                <>
                  <span>▶</span>
                  <span>Run Simulation</span>
                </>
              )}
            </button>
          </div>

          {/* RL-based Card */}
          <div
            style={{
              ...styles.card,
              ...(hoverCard === "rl" ? styles.cardHover : {}),
              borderColor: hoverCard === "rl" ? "rgba(16, 185, 129, 0.5)" : "rgba(71, 85, 105, 0.5)",
            }}
            onMouseEnter={() => setHoverCard("rl")}
            onMouseLeave={() => setHoverCard(null)}
          >
            <div
              style={{
                ...styles.cardIconWrapper,
                background: "rgba(16, 185, 129, 0.2)",
              }}
            >
              <span style={{ fontSize: "32px" }}>🧠</span>
            </div>
            <h3 style={styles.cardTitle}>RL-Based</h3>
            <p style={styles.cardDescription}>
              Advanced reinforcement learning approach
            </p>

            <div style={styles.paramBox}>
              <div style={styles.paramLabel}>Parameters:</div>
              <div style={styles.paramTags}>
                <span
                  style={{
                    ...styles.paramTag,
                    background: "rgba(16, 185, 129, 0.2)",
                    color: "#6ee7b7",
                  }}
                >
                  --proximity 250
                </span>
                <span
                  style={{
                    ...styles.paramTag,
                    background: "rgba(16, 185, 129, 0.2)",
                    color: "#6ee7b7",
                  }}
                >
                  --steps 1000
                </span>
                <span
                  style={{
                    ...styles.paramTag,
                    background: "rgba(16, 185, 129, 0.2)",
                    color: "#6ee7b7",
                  }}
                >
                  --model DQN
                </span>
              </div>
            </div>

            <button
              onClick={() => handleRun("rl")}
              disabled={loading}
              style={{
                ...styles.button,
                background: loading && activeMethod === "rl"
                  ? "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                  : "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                ...(loading ? styles.buttonDisabled : {}),
              }}
              onMouseOver={(e) => {
                if (!loading) {
                  e.currentTarget.style.transform = "scale(1.02)";
                  e.currentTarget.style.boxShadow = "0 10px 30px rgba(16, 185, 129, 0.4)";
                }
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.transform = "scale(1)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              {loading && activeMethod === "rl" ? (
                <>
                  <div style={styles.spinner}></div>
                  <span>Running...</span>
                </>
              ) : (
                <>
                  <span>▶</span>
                  <span>Run Simulation</span>
                </>
              )}
            </button>
          </div>
          </div>

          {/* Footer Info */}
          <div style={styles.footer}>
            <p>
              Backend running on{" "}
              <span style={styles.footerHighlight}>localhost:5000</span>
            </p>
            <p>
              <button
                onClick={() => {
                  // navigate to /live
                  window.history.pushState({}, '', '/live')
                  window.location.reload()
                }}
                style={{
                  marginTop: 12,
                  padding: '8px 14px',
                  borderRadius: 8,
                  border: '1px solid rgba(71,85,105,0.4)',
                  background: 'transparent',
                  color: '#93c5fd',
                  cursor: 'pointer'
                }}
              >
                Analyze (Live)
              </button>
            </p>
          </div>
        </>
        )}
      </div>
    </div>
  );
}

export default App;