DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

INSERT INTO `user` (`name`, `token`, `leader_card_id`) VALUES
('ほのか', 'abcde', 1),
('うみ', 'efghij', 2),
('ゆうき', 'klmnop', 3),
('ひなた', 'qrstuv', 4),
('みずき', 'wxyz', 5);

UPDATE `user` SET `name`='ひろや' WHERE `id` = 5;
