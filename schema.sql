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
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint NOT NULL,
  `owner` bigint NOT NULL,
  `status` int NOT NULL,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL ,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  `score` int,
  `judge_perfect` int DEFAULT 0,
  `judge_great` int DEFAULT 0,
  `judge_good` int DEFAULT 0,
  `judge_bad` int DEFAULT 0,
  `judge_miss` int DEFAULT 0,
  `game_ended` boolean DEFAULT FALSE,
  PRIMARY KEY (`room_id`,`user_id`)
);
