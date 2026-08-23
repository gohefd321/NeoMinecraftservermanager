package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

//go:embed static/index.html
var indexHTML []byte

type SetupPayload struct {
	NodeRole       string `json:"node_role"`
	NodeName       string `json:"node_name"`
	NodeID         string `json:"node_id"`
	MasterEndpoint string `json:"master_endpoint,omitempty"`
	ClusterToken   string `json:"cluster_token,omitempty"`
	HardwareTier   string `json:"hardware_tier,omitempty"`
	AdminEmail     string `json:"admin_email,omitempty"`
	MasterSecret   string `json:"master_secret,omitempty"`
}

var (
	validIdentifier = regexp.MustCompile(`^[a-zA-Z0-9_\-\.]{3,64}$`)
)

func sanitizeInput(s string) string {
	return strings.TrimSpace(s)
}

func handleSetupComplete(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, `{"error":"Method not allowed"}`, http.StatusMethodNotAllowed)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, `{"error":"Failed to read request"}`, http.StatusBadRequest)
		return
	}

	var payload SetupPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		http.Error(w, `{"error":"Invalid JSON payload"}`, http.StatusBadRequest)
		return
	}

	payload.NodeRole = sanitizeInput(payload.NodeRole)
	payload.NodeName = sanitizeInput(payload.NodeName)
	payload.NodeID = sanitizeInput(payload.NodeID)

	if !validIdentifier.MatchString(payload.NodeID) || !validIdentifier.MatchString(payload.NodeName) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"error":"Node ID and Node Name must be 3-64 alphanumeric characters, dashes, or underscores"}`))
		return
	}

	// /etc/nextgen-mc 구성 디렉토리 생성
	configDir := "/etc/nextgen-mc"
	if err := os.MkdirAll(configDir, 0750); err != nil {
		log.Printf("Failed to create config dir: %v", err)
	}

	envFilePath := filepath.Join(configDir, "node.env")
	var envBuilder strings.Builder
	envBuilder.WriteString(fmt.Sprintf("NODE_ROLE=%s\n", payload.NodeRole))
	envBuilder.WriteString(fmt.Sprintf("NODE_NAME=%s\n", payload.NodeName))
	envBuilder.WriteString(fmt.Sprintf("NODE_ID=%s\n", payload.NodeID))

	if payload.NodeRole == "worker" {
		if payload.HardwareTier == "" {
			payload.HardwareTier = "standard_ssd"
		}
		envBuilder.WriteString(fmt.Sprintf("MASTER_ENDPOINT=%s\n", sanitizeInput(payload.MasterEndpoint)))
		envBuilder.WriteString(fmt.Sprintf("CLUSTER_TOKEN=%s\n", sanitizeInput(payload.ClusterToken)))
		envBuilder.WriteString(fmt.Sprintf("HARDWARE_TIER=%s\n", sanitizeInput(payload.HardwareTier)))
	} else {
		envBuilder.WriteString(fmt.Sprintf("ADMIN_EMAIL=%s\n", sanitizeInput(payload.AdminEmail)))
		envBuilder.WriteString(fmt.Sprintf("MASTER_SECRET=%s\n", sanitizeInput(payload.MasterSecret)))
	}

	if err := os.WriteFile(envFilePath, []byte(envBuilder.String()), 0600); err != nil {
		log.Printf("Warning: could not write to /etc/nextgen-mc/node.env (fallback local): %v", err)
		_ = os.WriteFile("./node.env", []byte(envBuilder.String()), 0600)
	}

	// Systemd 서비스 생성 및 구동 (root 권한인 경우)
	serviceName := "mc-master"
	if payload.NodeRole == "worker" {
		serviceName = "mc-worker"
	}

	go func() {
		time.Sleep(1500 * time.Millisecond)
		log.Printf("[Wizard] Configuring and launching systemd service: %s", serviceName)
		_ = exec.Command("systemctl", "daemon-reload").Run()
		_ = exec.Command("systemctl", "enable", "--now", serviceName).Run()
		log.Printf("[Wizard] Setup complete. Exiting setup wizard process.")
		os.Exit(0)
	}()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(fmt.Sprintf(`{"status":"success","message":"%s 노드 설정이 완료되었습니다. 서비스가 활성화됩니다."}`, payload.NodeRole)))
}

func main() {
	port := os.Getenv("WIZARD_PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()

	// 1. 임베디드 HTML 서빙 (어느 작업 디렉토리에서 실행해도 404 방지)
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		w.Write(indexHTML)
	})

	mux.HandleFunc("/api/setup/complete", handleSetupComplete)

	server := &http.Server{
		Addr:         ":" + port,
		Handler:      mux,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
	}

	log.Printf("==========================================================")
	log.Printf("🚀 NextGen MC Platform Web Setup Wizard is running!")
	log.Printf("👉 Access Web Wizard at: http://0.0.0.0:%s", port)
	log.Printf("==========================================================")

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("Server error: %v", err)
	}
}
