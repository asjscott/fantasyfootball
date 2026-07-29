package api

import (
	"encoding/json"
	"log"
	"net/http"
)

type APIError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type Envelope struct {
	Data  any       `json:"data"`
	Error *APIError `json:"error"`
	Meta  any       `json:"meta"`
}

func writeJSON(w http.ResponseWriter, status int, body Envelope) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(body); err != nil {
		log.Printf("failed to encode response: %v", err)
	}
}

func WriteData(w http.ResponseWriter, status int, data any, meta any) {
	writeJSON(w, status, Envelope{Data: data, Error: nil, Meta: meta})
}

func WriteError(w http.ResponseWriter, status int, code string, message string) {
	writeJSON(w, status, Envelope{Data: nil, Error: &APIError{Code: code, Message: message}, Meta: nil})
}
