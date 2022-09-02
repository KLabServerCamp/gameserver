DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NOT NULL,
  `token` varchar(255) DEFAULT NOT NULL,
  `leader_card_id` int DEFAULT NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);
