-- +goose Up

ALTER TABLE predictions ADD COLUMN confidence NUMERIC;

-- +goose Down

ALTER TABLE predictions DROP COLUMN confidence;
