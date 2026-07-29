package main

import (
	"context"
	"log"
	"net/http"

	apihandlers "fantasyfootball/api/internal/api"
	"fantasyfootball/api/internal/config"
	"fantasyfootball/api/internal/db"
	"fantasyfootball/api/internal/store"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("config error: %v", err)
	}

	ctx := context.Background()
	pool, err := db.NewPool(ctx, cfg.DatabaseURL)
	if err != nil {
		log.Fatalf("database connection error: %v", err)
	}
	defer pool.Close()

	handlers := &apihandlers.Handlers{Queries: store.New(pool)}

	mux := http.NewServeMux()
	handlers.Register(mux)

	addr := ":" + cfg.Port
	log.Printf("listening on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
