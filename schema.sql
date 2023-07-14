use webapp;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` int NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `owner_id` bigint NOT NULL,
  `max_user_count` int NOT NULL DEFAULT 4,
  `is_game_started` boolean NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`)
);


DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_game_finished` boolean NOT NULL DEFAULT 0,
  `latest_score` int DEFAULT NULL,
  `latest_num_perfect` int DEFAULT NULL,
  `latest_num_great` int DEFAULT NULL,
  `latest_num_good` int DEFAULT NULL,
  `latest_num_bad` int DEFAULT NULL,
  `latest_num_miss` int DEFAULT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);
