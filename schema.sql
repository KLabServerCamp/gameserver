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
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `room_id` bigint NOT NULL,
  `joined_user_count` int DEFAULT NULL,
  `max_user_count` int DEFAULT NULL,
  `status` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `room_id` (`room_id`)
);


DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `name` varchar(255) DEFAULT NULL,
  `user_id` bigint NOT NULL,
  `room_id` bigint NOT NULL,
  `token` varchar(255) DEFAULT NULL,
  `select_difficulty` int DEFAULT NULL,
  `is_host` boolean DEFAULT NULL,
  PRIMARY KEY (`room_id`, `user_id`),
  CONSTRAINT `fk_1` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_2` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  UNIQUE KEY `token` (`token`)
);


DROP TABLE IF EXISTS `room_score`;
CREATE TABLE `room_score` (
  `user_id` bigint NOT NULL,
  `room_id` bigint NOT NULL,
  `score` int DEFAULT NULL,
  `perfect_count` int DEFAULT NULL,
  `great_count` int DEFAULT NULL,
  `good_count` int DEFAULT NULL,
  `bad_count` int DEFAULT NULL,
  `miss_count` int DEFAULT NULL,
  PRIMARY KEY (`room_id`, `user_id`),
  CONSTRAINT `fk_3` FOREIGN KEY (`room_id`) REFERENCES `room` (`room_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_4` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
);
