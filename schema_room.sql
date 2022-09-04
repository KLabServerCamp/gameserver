DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `owner` bigint NOT NULL,
  `status` int DEFAULT 1,
  `joined_user_count` int DEFAULT 1,
  `max_user_count` int NOT NULL,
  PRIMARY KEY (`id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `difficulty` int NOT NULL,
  `score` int DEFAULT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);

DROP TABLE IF EXISTS `room_result`;
CREATE TABLE `room_result` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `perfect` int NOT NULL,
  `great` int NOT NULL,
  `good` int NOT NULL,
  `bad` int NOT NULL,
  `miss` int NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);