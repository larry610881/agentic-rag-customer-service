-- Remove wiki knowledge graph feature
DROP TABLE IF EXISTS wiki_graphs;
ALTER TABLE bots DROP COLUMN IF EXISTS wiki_navigation_strategy;
