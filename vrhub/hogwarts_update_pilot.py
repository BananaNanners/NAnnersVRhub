# SPDX-License-Identifier: GPL-3.0-only
"""Read-only review of the pinned Hogwarts Legacy profile update."""
from collections import Counter
from dataclasses import replace
from hashlib import file_digest, sha256
import json
from pathlib import Path
from zipfile import ZipFile

from . import hub, profile_safety

ARCHIVE_SHA256 = "d2fb2b74db85dc2bab039063b367016a4a30fe5dfd509bb3480da0a0cde87efb"
SOURCE = "https://github.com/jbusfield/HL_UEVR/releases/tag/v2.1.0"
BASELINE = "30d7e626882bb3a7e1d04d8a42fd4f4bbcda9011054c4b12bf9e6e722dab06a3"
# Exact historical JSON bytes, embedded for the already released 0.5.4
# managed installer, which copies Python modules but not recipe JSON.
BASELINE_JSON = (
    b'{\n'
    b'  "archive_sha256": "30d7e626882bb3a7e1d04d8a42fd4f4bbcda9011054c4b12bf9e6e722dab06a3",\n'
    b'  "files": {\n'
    b'    "cache/sdk_discovery.json": "7453f206cae27120c2e20ddd3c9bce6d59c280f4799b1d725cfe9adc9a039ff0",\n'
    b'    "cameras.txt": "1965e554445940aff8c0d0abf7efea4f121d4bbd99f41b00a576e3a3ab69d380",\n'
    b'    "config.txt": "2b016b7e72b5f6b645715edc68d5c81d5930004aa774d1b2b8ef622dd5c30b0d",\n'
    b'    "cvars_data.txt": "6edbd206e2a05fca4ead14480ba33e57759ddd1a6bcd981785f3ae8426b78d24",\n'
    b'    "data/accessories_parameters.json": "d475fdddd6d7f70b54bbf1d743abe32e750624eefdad4e7f003eb363b3f9f2aa",\n'
    b'    "data/attachments_parameters.json": "dbd274f264515265f8a62c7ff06e80b17d3f8c9c280775fa3fda80e2648a852d",\n'
    b'    "data/collision_parameters.json": "7c21d4e1c79af18b7707df62c13d4629b5146b3a6a931dc85286d5cbe3007eab",\n'
    b'    "data/config__flicker_fixer.json": "cbe37bd1e10b7e3c2a7eecbe5f5664a1da4622fddadcadfe92b8abd101f55dfa",\n'
    b'    "data/config_default.json": "16502f9504705b6cb5df3a43c8e3216295c43e1e47b6748c449443ec6ce8347f",\n'
    b'    "data/config_dev_utils.json": "1de9697f8bbc6e072bfb244d0c24c5ac497854038558c43328aec9fe9ead7793",\n'
    b'    "data/dev/attachments_config_dev.json": "5ed2bc17dad87c8acf4a2a62cfd03c88b9546055a03ae1dffb9879ef0938f5c2",\n'
    b'    "data/dev/collision_config_dev.json": "9a056db8e78d2db589a5ec69c9ef600bf7babb7431e9ab2deb1f7aa81380a071",\n'
    b'    "data/dev/gesture_config_dev.json": "7b256b4a46b6009b6cd8e645aeeb367911ff576b48125957894e363f768c6e41",\n'
    b'    "data/dev/gesture_trainer_config.json": "a9666a1bd8815c26924567ebd120cac416550f3f7f58a0b8e61b1924ae46262a",\n'
    b'    "data/dev/gesture_trainer_parameters.json": "b1ae57ccc1ecc619a472c17bd4920b8ccaa54b92f2017e526dfece633caf9454",\n'
    b'    "data/dev/ik_config_dev.json": "a8313623ad2f4d55e35d1de6637e4419731b852c6d77030226c528945d982472",\n'
    b'    "data/dev/input_config_dev.json": "acdb7718d6868be7c8c88980b89304281cb907be967fb74a63d597aed31c93b9",\n'
    b'    "data/dev/montage_config_dev.json": "15eaa533996fdf5187bc24550c74019c246e53323485abf8d9b3661b5b95793a",\n'
    b'    "data/dev/particles_config_dev.json": "dd291a588dd9e1464de98a699c367d6eb84f9bd69691e2f9f5dcb94f149c6bb3",\n'
    b'    "data/dev/pawn_config_dev.json": "5932c5b7509b4963f5a7c3728a66527642927c5b26a76f1f62a49638be88cf42",\n'
    b'    "data/dev/reticule_config_dev.json": "b44c0850ad1e502fc81ba3d7d20c5600d866308e464d4297b42e6f37dd4b2b2d",\n'
    b'    "data/dev/ui_config_dev.json": "5d242bbc6db3432949c9f02599bcb61e6c0d3b846f94942bc6ad1612e29e5207",\n'
    b'    "data/dev/widgetcomponent_config_dev.json": "6bbb371fc56ffdb7f9f7bb1ab18eccf3ad90de73e8e9c9eba2c2eebb56b40eb3",\n'
    b'    "data/gesture_parameters.json": "233cf7c91b088abbc6d4c6b3fc02faf4bbc71a5c81556fec5d1cc91cd52121f5",\n'
    b'    "data/gunstock_config.json": "80868ecf1fb6499e5b2037bdefb83ffe06d954603c476d0ff717add7ab643ead",\n'
    b'    "data/gunstock_parameters.json": "f629cb7e83641e66d51d557e57be0bdb0019be901b1fe3bdea366f7f30ba3be9",\n'
    b'    "data/hands_creator_config.json": "a229f040aad005aea6e10c4f16e001753cdf6b0137d6562ad8175d7aeecd99e1",\n'
    b'    "data/hands_parameters.json": "488173e0a7d29e0df31264e1cb284708de3036c96a753089af0943fd0c8f14c4",\n'
    b'    "data/hogwarts_config.json": "63ae64a7bace57474bbaf3d9bca7b689c02dc131871cb5a4a9afc33f5906c365",\n'
    b'    "data/hogwarts_legacy_config.json": "a173b2eeb027f6dee95e3ee2dda92c8df97877ce3537c6c7bf1edaa30338ea66",\n'
    b'    "data/ik_parameters.json": "07fe66d78a9a8c9e46277bdf8c638a162920ba0fbf11b5dae7707373bc58e18e",\n'
    b'    "data/images/Accio.png": "928259b38d04d1802e40b0961c187d97cef0089f8a6c109bfeae3e3c156a2600",\n'
    b'    "data/images/Alohomora.png": "2becd52a48b935dc0388c593faf06ebf10a8873eb80d25c306646266c45c2e49",\n'
    b'    "data/images/ArrestoMomentum.png": "6f9fe91f6ac3b5636f3edd5191165dfde2cda4c28c154ab31e4e9c0c49a95b12",\n'
    b'    "data/images/AvadaKedavra.png": "0ebe173a6bbb9a7632de8957725db9891c5f8117dee7aa63d1d256c6406a839a",\n'
    b'    "data/images/Bombarda.png": "0e043b45a1510598eb852aa9c12ccdb221ae4dc8b35c90ce22e045b9d1886a53",\n'
    b'    "data/images/Confringo.png": "c11f4fa4aa588430f0d652e0372e54e01a8c40924b62f56deafdcf2c74a46229",\n'
    b'    "data/images/Conjuration.png": "99fee245538add54c19ad0a8f63e2a89447fde436b7b25da92d7a689678cdeb8",\n'
    b'    "data/images/Crucio.png": "185e996e690a3053af5a0b29d9bd1cd5afcb713d47ad38a53f056575ce77b480",\n'
    b'    "data/images/Depulso.png": "c3abfe94533d0ab9a8b70a8eb2fe6669e0e622ba388ec9118099ae5d0d256351",\n'
    b'    "data/images/Descendo.png": "9c60d7a20292278a2f769c524ff8586b1f674786fa012627f813bb2bacad823f",\n'
    b'    "data/images/Diffindo.png": "108b5538b27aae28d3233ed2a9d2e1c6f5839f9ea84cbc231cc4b5d8f4165193",\n'
    b'    "data/images/Disillusionment.png": "aae968202184507e92a524f130aff5cffe8c9dc9212d4e9fc7fa63f1fbcf678a",\n'
    b'    "data/images/Expelliarmus.png": "c6ef4a95abb047d4656ccaa89df9eb3306499a22e83c9d33b8a31863c56d903f",\n'
    b'    "data/images/Flipendo.png": "ad1ad853a73f94be998160c4f3919b8cd183b5a931075ae44d9f64ef0ef75c36",\n'
    b'    "data/images/Glacius.png": "ab4a32c147bee91f8aee736ea123c7fadcb4a74b4598fc9e8223f2c925ee5dd1",\n'
    b'    "data/images/Imperius.png": "24dd1204170bc392cc5e438581ccf16766dddbfeb3904237bfec6fe723afa11e",\n'
    b'    "data/images/Incendio.png": "2aaff2ca8e84a2d3b6d7d497cd98e6654fe5fbd39635362171cce76daffccae8",\n'
    b'    "data/images/Levioso.png": "55e2f99747490add4952978c5b3a8a7b887518c2d3ccfff48e60fd8a6634d02f",\n'
    b'    "data/images/Lumos.png": "6decf68cf0b413a85ea7c1990eed74c79357364b4b2c65b383c61b474687f334",\n'
    b'    "data/images/Nutritio.png": "a3068f2edc96a701d21c8c3bf2d8a11c812f32e2daf7bbf97b2c8a415e68d6a0",\n'
    b'    "data/images/Oppugno.png": "0055a484a3debca833352730c59f84a1c6c959b7f59fa8b34c40f1defc89d7f5",\n'
    b'    "data/images/Petrificus.png": "e458ddfe21469576078e026c021d1c19bdafe2aa9bce7af4b214a79c67c4bc5c",\n'
    b'    "data/images/Placato.png": "ebfd305cf8076f51b99a4a14e934c0169a825973b0fbfa8ddd535436e1319d5d",\n'
    b'    "data/images/Reparo.png": "f8333916ff3b03996f9f1c0fd88e4dbeb1c562099ba98e1784c57cf0c3c3c95d",\n'
    b'    "data/images/Revelio.png": "fdfdae79385fae99c50b53553590c138a3da9bcee8ca22bb3d6f264477e8568f",\n'
    b'    "data/images/Sanctuarium.png": "172c473c4be78793e2bbbb49eceb6ac354692972828bc37d095809c4289a261b",\n'
    b'    "data/images/Tormentum.png": "83780ec78c5becf2fa593965c46997ef823537274efe8b21cae18f6275c07ee5",\n'
    b'    "data/images/Transformation.png": "bbd3b0abdd9e7bd8bacbd45b6e1e8df41119a2b843ad781a4752570e3be313ef",\n'
    b'    "data/images/TransformationOverland.png": "37200deddbd84483f0ee398ccb19229ec04ea55a9565e62e993d2671f5bb4f6d",\n'
    b'    "data/images/Vanishment.png": "7970b7f4b4820e3568b10617792e5400c55558c0fd68a42ea67b1e858df7f30d",\n'
    b'    "data/images/Viaspecto.png": "2ad4e448acaea8cf8d087b42ae138598ea67e233d809cf861b3f3db2f8ab3b83",\n'
    b'    "data/images/Wingardium.png": "be2ef3587acb314556f33a7c741f377d590491af0250b1fd48e840a45d3b7324",\n'
    b'    "data/images/glyph-16.png": "7d97fb331ac6aab0262420c27d641649b7b943c3d30703ce9fd4fdf851196787",\n'
    b'    "data/images/glyph-20.png": "39e065843f9f0d3727e40722cf1a06110dcb7c8be3ed60e66b5ed99a6111d55b",\n'
    b'    "data/images/glyph-26.png": "d07c89f06eab41e18a53d6249489d80ad5244c3dc52fcf5857f12b34a5683be2",\n'
    b'    "data/images/glyph-27.png": "2cf610dd29c1a406e238ca6cc89a1746570fec7c79be739413119c32bb63f63a",\n'
    b'    "data/images/glyph-30.png": "914f35071514410f26bf728f000d52c1dbf2a5c2b19b5feda613958f8054a6ed",\n'
    b'    "data/images/glyph-36.png": "5e35373a8ee99ae25e8dc8e7870a299650d9c2d8f84ccedc8b0b4ba52d7e1b68",\n'
    b'    "data/input_parameters.json": "c90c592a4d79610be751913e43e6324326adade518ba4ea9a6a9d13a6dd5cd35",\n'
    b'    "data/interaction_config_dev.json": "3fb81b42f10bf0d675617fb2cd2def9b100d92a2c307e91d449225719aa9dfb2",\n'
    b'    "data/montage_parameters.json": "88693180611789d358838b2ef6bc04067f468a58cd9cc408f1994ef83fa1ac17",\n'
    b'    "data/particles_parameters.json": "c0e95d941fa795565af812aba9028b319dcbdd1d0f9075a46dac6012a4bba1f6",\n'
    b'    "data/pawn_parameters.json": "3b5a973088630993d499622d29e7079ab6cae57e9f4666295db657934f7fd732",\n'
    b'    "data/remap_config_dev.json": "9b52747c7adb494940c092af57dc8591cb8e2848099930346c573a1d0ab30bf4",\n'
    b'    "data/remap_parameters.json": "675f31f6376c579e461a5e7790f4445688a7a704d938f64d56b01f5ef167cd1c",\n'
    b'    "data/reticule_parameters.json": "24b3d3a4cb0c914612ec9a57d9c9efeac546baeba10f9724e0f35cfd961b5430",\n'
    b'    "data/ui_parameters.json": "309c7d970df3919e02e9a54ca405455feef2e933c8d657f11c992e470a5f3229",\n'
    b'    "data/widgetcomponent_parameters.json": "e5b1b19682f55da9c30aaefd5616486e8a1f6d7366144889d78a8437762fa2c2",\n'
    b'    "data/widgetcomponent_user_parameters.json": "bfee5866c63cf7d8509cac766a93e52ea45de35159216f19d9af831ee55d0f52",\n'
    b'    "imgui.ini": "4033576df9c67b65b90f3a53123e1aeaaeb2c0926d76b7e378223a248096f7ea",\n'
    b'    "plugins/gesture/model.onnx": "04f6eaaf9a107f987452e54ec32e071c988420b1d20c8f1af06af682d5f7884a",\n'
    b'    "plugins/gesture_recognizer.dll": "0d25bb8f955a1dba44c5c9798bfcf9dfed7b2bd83fb94bb473d793975e3e753e",\n'
    b'    "plugins/ort/onnxruntime.dll": "b95efb2113b603bbbf3f191061c5516a871ed546893c820e4f3b7b6c358dbf2a",\n'
    b'    "plugins/ort/onnxruntime_providers_shared.dll": "f2540b89707b47895c2a732bfd04e34a695c580d22301ef44c0f01f09b001673",\n'
    b'    "plugins/uevr_utils.dll": "7cd73aece0ab695ac792e45ca6257d91955cf19f1b60fa4d911c93c907cd4a2c",\n'
    b'    "plugins/voice/embedding_model.onnx": "70d164290c1d095d1d4ee149bc5e00543250a7316b59f31d056cff7bd3075c1f",\n'
    b'    "plugins/voice/melspectrogram.onnx": "ba2b0e0f8b7b875369a2c89cb13360ff53bac436f2895cced9f479fa65eb176f",\n'
    b'    "plugins/voice/models/Accio.onnx": "ee8eb5ace18a13ba4044786b0f1b777b93133061c987ddbf33aa4e6c0bdc927f",\n'
    b'    "plugins/voice/models/Alohomora.onnx": "be1389a8b35de4aaa1b3262398c1617c05a2016c7ceae447d031ff2fd0cae15c",\n'
    b'    "plugins/voice/models/ArrestoMomentum.onnx": "0ff9a93d148d3d10cb14ca4c25ea03280b053ce2ffd3f0fb49b92f0a6804947c",\n'
    b'    "plugins/voice/models/AvadaKedavra.onnx": "2249c097a5408fdc4f7f67f5d80648960f69b58a51130797fe6922c89a3d5110",\n'
    b'    "plugins/voice/models/Bombarda.onnx": "f1f9a5dae320cfa09a4de86341630a453d2472f43f5802ac71b498738b996df5",\n'
    b'    "plugins/voice/models/Confringo.onnx": "06bb04c831f810e214aa60cdfc2b5db8210c76fc4532767f68b8850786c8e5d8",\n'
    b'    "plugins/voice/models/Conjuration.onnx": "57ae5bbd544e6045ad46e7ef14a22effb874fc0ff2c9dd3bd8f07c22e4111f8e",\n'
    b'    "plugins/voice/models/Crucio.onnx": "8ed035477ae53c8d41d483e1fccd0d9c12a6d58744fbb77afd887961c3344a2c",\n'
    b'    "plugins/voice/models/Depulso.onnx": "04c6e690401a960c23c7ac0cfa784bdc83144a2c962780df0be269bab4b35fc3",\n'
    b'    "plugins/voice/models/Descendo.onnx": "a2431f01b9796cf61b4c804cef047c5d132252a0bc5162e6cc017566b14a47d8",\n'
    b'    "plugins/voice/models/Diffindo.onnx": "5c8834db3c0d2f8a5ca1641e0b74427320c0b220341a16806b23d24e6f0ad171",\n'
    b'    "plugins/voice/models/Disillusionment.onnx": "8c3354f1d5e66007100d0ae5c96b9c93312d65ee5b42b9335a661da6ef223a57",\n'
    b'    "plugins/voice/models/Expelliarmus.onnx": "7cff68a94831e4c6f8370ba724c956b276b6dfa4622530e49000105c1e2aaba6",\n'
    b'    "plugins/voice/models/Flipendo.onnx": "2c1e1942239afadf7dcb58411b0ddb832fb76a709393360213d2c50a0efb71b1",\n'
    b'    "plugins/voice/models/Glacius.onnx": "35f6eab0faa2b8b6005dc24add7d5bd6f3cdbf41b5a1b3154eb1bad0570b43f9",\n'
    b'    "plugins/voice/models/Imperius.onnx": "b07907085f06b3073facd1079b96401a88e8ce8d09874a08ed42a3b83be18fe2",\n'
    b'    "plugins/voice/models/Incendio.onnx": "7536283e2774cc5e8bc74c1aa57e8eeae537a262b4da2c2426033995e62dd7c4",\n'
    b'    "plugins/voice/models/Levioso.onnx": "f5837dc92abf0465b64428f20ebc4881e123f9505ddaf5f38d3d64dfcca0fb25",\n'
    b'    "plugins/voice/models/Lumos.onnx": "372ac239d4364f7ee73f6b8cadaf84df69b54bf9a90eea6f9e124991e95cc449",\n'
    b'    "plugins/voice/models/Nutritio.onnx": "2f422eb1e7c5f9b4d331d7990cc05773b83105766751b29a9c5fe900d8097b57",\n'
    b'    "plugins/voice/models/Oppugno.onnx": "4a00a84ad5e0292403427d9bbce5979b766f0092d1166bfc8ef4d1e69ee21585",\n'
    b'    "plugins/voice/models/Petrificus.onnx": "90d96bc0a7fa769b8d4c51d4749b32f95c9f629a89814ee58d2649cd6fc86219",\n'
    b'    "plugins/voice/models/Placato.onnx": "25dc7075f16c33e25398ce917c859051ef816ab4a4d66b40dda3f2d60a5bf72d",\n'
    b'    "plugins/voice/models/Reparo.onnx": "2acc7aa1c8f9f032dd7ef43593a72afdcfa7dae09ca455eb569ae0ed59d5f38c",\n'
    b'    "plugins/voice/models/Revelio.onnx": "06679b1fa32c6e56100a2302529c8720ee392b9e25a567c34a88c97ebd6d9a9e",\n'
    b'    "plugins/voice/models/Sanctuarium.onnx": "e73e2e6c34153906ffacea10507b7f6795835a0276fa350129dabc4c7a5f3e10",\n'
    b'    "plugins/voice/models/Tormentum.onnx": "82c2a82d9925a3dea993d63743ae76a42cf780538c19a8fe45de2d14be81cb56",\n'
    b'    "plugins/voice/models/Transformation.onnx": "d6e0f49c868f95bea9c09749f86b18831bdd28562b1d5d1a52d40228cc1a2fb5",\n'
    b'    "plugins/voice/models/TransformationOverland.onnx": "94670d6ec8a860c2eec19f1d4c0605de5090bb2eae53601a16e125b452e72ceb",\n'
    b'    "plugins/voice/models/UpBroom.onnx": "cac1e52e54e8dd07bc9f978f229c9111ece57508dd51e4c6db572e26659c5398",\n'
    b'    "plugins/voice/models/UpGraphorn.onnx": "138518c6121a50c6d8c8612ecc2560d40fa963541a04d0c954fdc3ec33b91eef",\n'
    b'    "plugins/voice/models/UpHippogriff.onnx": "11918fe4dbbdb5f84cbd85a943b909c1381665b49cc870f3548ecc0d3967d33d",\n'
    b'    "plugins/voice/models/Vanishment.onnx": "dfbdc1aa77dfaab9e60e5da91f32f5033c093cf4ac79c491dfb42c07de1eb931",\n'
    b'    "plugins/voice/models/Viaspecto.onnx": "d48eb2e02fd6846a9a20c1ed2e085dfb8a32e856e9ee4a9eed8470f2680f4222",\n'
    b'    "plugins/voice/models/Wingardium.onnx": "36d609c0a9363da90ef41def8457fbdad3b134df291cac971fafe38c4925e9bb",\n'
    b'    "plugins/voice_recognizer.dll": "204131746f0b5ed6628d1f4cba9a246837ff3c082ba8a9bfe54847f3b02c7fb8",\n'
    b'    "scripts/helpers/interactions.lua": "952e78942beec2c604d44b0dc719a15d3d5cd0bd301b446f52e7cf9e71b28448",\n'
    b'    "scripts/helpers/locomotion.lua": "cfebb9f86604daa7809366949029983bda36fbc7b66f0c45e010c52b8ab7efee",\n'
    b'    "scripts/helpers/mounts.lua": "009ab1bdb3b7456590a581b78281c9a372f21c2e8b908eef4e7dd19533763d29",\n'
    b'    "scripts/helpers/spells.lua": "3f92780a26bd86647ff3ffe72c5d3b39d09addbd3fb8cbf521ccfe91ede36ce4",\n'
    b'    "scripts/libs/.vscode/settings.json": "cf868c604fbb30e4f817f64f426af2ed544d33b760562e26673fb0b31e8683ef",\n'
    b'    "scripts/libs/accessories.lua": "20eb51ba23ac65c8404a4f2b41871c014d2cf82584c00c5786aebd9d1c2697f1",\n'
    b'    "scripts/libs/animation.lua": "4c34702d8fe467b6a19d85f9ab50639ad079601472ed6ca861b17d2e80179e29",\n'
    b'    "scripts/libs/attachments.lua": "1adf57ad116b2ffc37bc2810023d97df90557f68dd61d666fe6dcc4b7e1b3247",\n'
    b'    "scripts/libs/body_yaw.lua": "27a4e29c862b5eca7f08097bb6fdc05f0d967b91f17cd11e0e53de01cba73e00",\n'
    b'    "scripts/libs/collision.lua": "9c01523db0edb659fb0173e2f202f79313b0728ed11a7fff4c328ad540a39a49",\n'
    b'    "scripts/libs/config/accessories_config_dev.lua": "c30ca7ab7cf098e564470a54e9420b72ee0de682286cad34d61faa5e453b787d",\n'
    b'    "scripts/libs/config/collision_config_dev.lua": "1a892b20f961168b5827c04f65a30ef8182e4abc916a346fa7e43fe7508e4b00",\n'
    b'    "scripts/libs/config/gesture_config.lua": "904bffaa72c566393c150d09eced5af6b514e9a20883c58cb1356327dcf1cf2a",\n'
    b'    "scripts/libs/config/gesture_config_dev.lua": "1318ca4009e593473d0928fcd534020acf24131eb728cf89efe5fdf15dede1b7",\n'
    b'    "scripts/libs/config/gesture_trainer.lua": "7f8ea0c58359052eda7bc80c678ca6cc534f3c75e14e6e8d8a8c1714c4f8a06e",\n'
    b'    "scripts/libs/config/hands_config.lua": "f08bce8bd679a40d738c19f19b8079375c2b1e6da0ce90d741505b3cd5901d84",\n'
    b'    "scripts/libs/config/ik_config_dev.lua": "204e5240ae8d5f12c1c67acf384129feb0dedad44a1c7f22fb8542076cb89260",\n'
    b'    "scripts/libs/config/input_config.lua": "9c5da4f731a44b637616d186c3a2bd5a4e7e630c4d12278ce41bea6d697eb805",\n'
    b'    "scripts/libs/config/input_config_dev.lua": "b948bdd61b56cd0ccae11b09b64ddb7512188230a389067db56c71678b164e32",\n'
    b'    "scripts/libs/config/particles_config_dev.lua": "c8085b3ef3a704da29a81929f2d275ca5883fc01b11b0105c816764caa2021bf",\n'
    b'    "scripts/libs/config/pawn_config_dev.lua": "96c514177c636fe866e95ebcc8d321412c724820193a6825df1892b32c359a9a",\n'
    b'    "scripts/libs/config/reticule_config.lua": "2bad40d5a4e6ea6fb8e38ae339e161e53d8a4bdfca55fc3e3b1751d57f33c684",\n'
    b'    "scripts/libs/config/reticule_dev_config.lua": "ae8318f28094d5c8bb04e66a01273a5d5dfe2dc820307afa75290ab76340d7ee",\n'
    b'    "scripts/libs/config/ui_config.lua": "fb1600a0f40bd20bbe4eb6c2f5de83e16a52536a5709c34107b86cfb6ec56862",\n'
    b'    "scripts/libs/config/ui_config_dev.lua": "326e7c8ab870cc7a45472cde08088d5f375744dbf2c5669de843e84a9d61c3c1",\n'
    b'    "scripts/libs/config/widgetcomponent_config.lua": "5ee3ce9024c662bbd0a2327606930bf4bcf8578eb50344069fe4807afa8241f5",\n'
    b'    "scripts/libs/config/widgetcomponent_config_dev.lua": "d549deb171c44950c10529a3aea3505e747ac5441956eda0e97da88d7e56f31f",\n'
    b'    "scripts/libs/configui.lua": "7366ad7f89e6fd4c53633d0905d5c7a2556946c05b92f23585bd27fb58af72fd",\n'
    b'    "scripts/libs/controllers.lua": "d10a310bb988d57cf47ec84a53680f8db01e798d6270a6050f1ecf0239707263",\n'
    b'    "scripts/libs/core/lerp.lua": "01b15a52e2a295b5788a0aa82142e90b9c9fa359eb39f75a729e8e49f5f2d00e",\n'
    b'    "scripts/libs/core/math_lib.lua": "50eb591f8035940675b3f6d0c99e67cedde86509b1b3d945fee435455a15cba8",\n'
    b'    "scripts/libs/core/params.lua": "3c15c850ac43a2bde5b79d54a6d397481a504cd8aab5dde7568dcb70d39ee05a",\n'
    b'    "scripts/libs/core/plugin.lua": "eda2299ec1836f35dbd06e385d8af1ce4de0b23fca03b65a55b72fdbc6b5d5d8",\n'
    b'    "scripts/libs/core/tarray.lua": "4b61a775d84bacddf64e7642f1da29de28af19e308c1a5895222a4616d419876",\n'
    b'    "scripts/libs/core/uevr_lib.lua": "80de1062dc15bcc524a8fb6867357a6f0a7d240c113a0be488c7bde365863274",\n'
    b'    "scripts/libs/deprecated/input.lua": "8653fa50587c0d9a9f106bbfb65f3573c2bbe8412b37940ac4cb66cf627d19fd",\n'
    b'    "scripts/libs/deprecated/pawn.lua": "69926e370d66597099f33d14c98e71d114b0b38a46849e5514f83be5f3150063",\n'
    b'    "scripts/libs/deprecated/reticule.lua": "c696a28c4c10783e16827675b42a298e46cf983e2c7157174194bb5de7bbe2e9",\n'
    b'    "scripts/libs/deprecated/ui.lua": "f592d15f8fe3fa6fef4a3507db8fe89f4abf380c43470e8989d43e96984b3341",\n'
    b'    "scripts/libs/enums/input.lua": "ddf0aa2decf399b7d9f4d10d9bbf37ddd85810037bcfd72376c0388ca11d6e2a",\n'
    b'    "scripts/libs/enums/unreal.lua": "df78d650e61f88b09e9386c452bb32176c5688bb0d1e356e0578cd69d3db897b",\n'
    b'    "scripts/libs/flicker_fixer.lua": "76b061e19a8e39f012ab8efe86d62d127b9144903990e9676c05db55c7e8fd66",\n'
    b'    "scripts/libs/gestures.lua": "d1dc7c9134025f19b1ab38d9f7992d059cf0f3ed21d9204c99ca85f39590b768",\n'
    b'    "scripts/libs/gunstock.lua": "0c59428be4175db8093e2a69095f21fd5d3c8c953496abfd218ad9bf3a515964",\n'
    b'    "scripts/libs/hands.lua": "9f5558569669cfd64cb9ff6fb5c0842be311f53e04c3780485ea0a2cfc6ba298",\n'
    b'    "scripts/libs/hands_animation.lua": "33287ca2763c0b740d533e7e901f9ea992e77b77eac28438bc822f43ca8ff626",\n'
    b'    "scripts/libs/ik.lua": "1170cd3ecbd123abd8e8fbbbae0c1388686b0ee895fe1e15aea79e90bf55d51d",\n'
    b'    "scripts/libs/input.lua": "03bdb5e85f4fa894d5ebaa363bd4ca94897768b35df2fa82043df1b2d8f9e213",\n'
    b'    "scripts/libs/interaction.lua": "1d1e7b8760f51c365ddf4bab7d0bf9addb287ec7a93ee1142dd3978e90c79ff6",\n'
    b'    "scripts/libs/keyboard.lua": "e28755927c1e54fb60787d730da40e4c5cea9d82cd5840154b72c16ceba67dbf",\n'
    b'    "scripts/libs/laser.lua": "005aefe746bcad733b8c8ecc97294b4b30cd0b20fc8b02703d265c5a2bd7ef06",\n'
    b'    "scripts/libs/linetracer.lua": "3db07fce9fb5f209b491c1971b30d1c547031c0c576ea2015aec1d9f888a4c85",\n'
    b'    "scripts/libs/montage.lua": "fe69f578c41223f97bbf8fdefa59beb6210af2c7d55e1c1dcab329e60e67cba7",\n'
    b'    "scripts/libs/mouse.lua": "997c57083bd927edbb67a4a4732a3029ae7ad8480bd0320f8ab560be9f6c322d",\n'
    b'    "scripts/libs/particles.lua": "6eb64ba2133568a88e8df36adbe36ffbcc720b3e63437df80456b884a0788337",\n'
    b'    "scripts/libs/pawn.lua": "fa70676188cc24168e9761d0a3bfb3f29673bb054edd95f9df2ea1ea41746e10",\n'
    b'    "scripts/libs/physics.lua": "bc9c21493f6cd5da805ef90d4e67a8af9703c8d9468ff149e5d26a622a8e5d08",\n'
    b'    "scripts/libs/remap.lua": "29a60d2baf2b25290ab6f140978dece1cc002c7cf3e43781cb941b8f18d49f00",\n'
    b'    "scripts/libs/reticule.lua": "fb34cde4804b9265f931e9f87b3b57b0e7b4b3e76a2818b80789ca162c86007a",\n'
    b'    "scripts/libs/scope.lua": "17891dfc1f5b052959bd0f375be8ea9351a89282186d2ad092f4b20e2d673dc5",\n'
    b'    "scripts/libs/uevr_debug.lua": "29b81b2f5523b4a55b92180e5eca14a8a5e354aa912c50d570d41e49ba890b3e",\n'
    b'    "scripts/libs/uevr_dev.lua": "6c62627fa3ab709cc56670ec2f76890109d6d2536d9db82fe5a2df9cc627ea5a",\n'
    b'    "scripts/libs/uevr_utils.lua": "219614f2d5b3555eefaf21f3616843922b2112ff1aa03bc4ff23a3e2e7e0bc91",\n'
    b'    "scripts/libs/ui.lua": "3214a13e2f8dd93ada874f052e027eba66f49114c6998cdbf43a4aefce31bc8c",\n'
    b'    "scripts/libs/unit_test.lua": "1582b521eeb6bbc4ce3e76b8ee950a0432cd92d4231fd97994ecdccdb615cf1c",\n'
    b'    "scripts/libs/widget.lua": "685e374f8245d46773b43716d0da709f79a770e9f0c33e51b60785e6ebffcad8",\n'
    b'    "scripts/libs/widgetcomponent.lua": "65ce56afbdb702e1973d48e0c602e26bd121f05ebda28923bc7dd9831958317e",\n'
    b'    "scripts/main.lua": "beed19f63a058d624bf82de1e9e978d1df6a58a1fec48a9071f22fb194a9f50c"\n'
    b'  }\n'
    b'}\n'
)
BASELINE_JSON_SHA256 = "8c28927b2b7d5171b8031f467494a546c87c970cc9099d119d735d8635709eb4"


def baseline_reference():
    if sha256(BASELINE_JSON).hexdigest() != BASELINE_JSON_SHA256:
        raise RuntimeError("The official Hogwarts baseline resource changed.")
    reference = json.loads(BASELINE_JSON)
    if reference["archive_sha256"] != BASELINE or len(reference["files"]) != 192:
        raise RuntimeError("The official v2.0.6 baseline identity could not be verified.")
    return reference


LOCAL_FILES = {
    "cache/sdk_discovery.json", "config.txt", "data/config_default.json",
    "data/hogwarts_legacy_config.json", "imgui.ini",
}
COMPATIBILITY_BLOCK = (
    "The v2.1.0 maintainer recommends a clean profile. Compatibility of the updated Lua, "
    "plugins and input files with the preserved v2.0.6 settings has not been established. "
    "The update adds settings for stick drift and flick casting. "
    "Installation is disabled. config.txt stays active and config_AFW.txt stays separate."
)


def applies(recipe, archive):
    return (recipe["id"] == "hogwarts-legacy"
            and Path(archive).name.casefold() == "hogwartslegacy.zip")


def classify(current, baseline, incoming, owned):
    if (len(owned) != len(baseline) or set(owned) != set(baseline)
            or set(current) != set(baseline) | {"log.txt"}):
        raise RuntimeError("The installed files or Hub ownership differ from the reviewed v2.0.6 profile.")
    if not baseline.keys() <= incoming.keys() or "log.txt" in incoming:
        raise RuntimeError("The update changes the reviewed profile ownership boundary.")
    modified = {name for name in baseline if current[name] != baseline[name]}
    if modified != LOCAL_FILES:
        raise RuntimeError("Local modifications differ from the reviewed Hogwarts profile.")
    names = current.keys() | incoming.keys()
    if len({name.casefold() for name in names}) != len(names):
        raise RuntimeError("The installed and incoming paths conflict on Windows.")
    rows = []
    for name in sorted(names):
        if name == "log.txt":
            action, reason = "Preserve", "Existing player log"
        elif name in modified:
            action, reason = "Preserve", "Locally modified"
        elif name not in current:
            action, reason = "Install", "New v2.1.0 file"
        elif current[name] == incoming[name]:
            action, reason = "Preserve", "Already matches v2.1.0"
        else:
            action, reason = "Replace", "Matches the official v2.0.6 baseline"
        rows.append((action, name, reason))
    return tuple(rows)


def build_review(recipe, archive, steam_roots=None):
    base = profile_safety.build_plan(recipe, archive, steam_roots)
    if base.archive_sha256 != ARCHIVE_SHA256:
        raise RuntimeError(f"HogwartsLegacy.zip failed the pinned v2.1.0 SHA-256 check. Approved source: {SOURCE}")
    reference = baseline_reference()
    dest = Path(base.destination)
    snapshot = profile_safety._snapshot(dest)
    record = hub.state().get(f'{recipe["id"]}:profile') or {}
    try:
        owned = tuple(Path(name).relative_to(dest).as_posix() for name in record.get("files", ()))
    except ValueError as exc:
        raise RuntimeError("The Hub ownership record contains paths outside the reviewed profile.") from exc
    with ZipFile(archive) as data:
        incoming = {}
        for info, name in profile_safety._archive_entries(data):
            with data.open(info) as stream:
                incoming[name] = file_digest(stream, "sha256").hexdigest()
    dirs = {name.casefold() for name in snapshot["dirs"]}
    if any(name.casefold() in dirs for name in incoming):
        raise RuntimeError("An incoming file conflicts with an installed directory.")
    if profile_safety._digest(Path(archive)) != ARCHIVE_SHA256:
        raise RuntimeError("The archive changed while generating the review.")
    current = {name: item["sha256"] for name, item in snapshot["files"].items()}
    rows = classify(current, reference["files"], incoming, owned)
    if Counter(action for action, _, _ in rows) != {"Install": 36, "Replace": 53, "Preserve": 140}:
        raise RuntimeError("The installation actions differ from the reviewed update pilot.")
    return replace(base, blocked=(COMPATIBILITY_BLOCK,)), rows
