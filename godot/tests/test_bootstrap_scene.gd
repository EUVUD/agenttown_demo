class_name BootstrapSceneTest
extends GdUnitTestSuite


func test_bootstrap_scene_has_the_expected_inert_contract() -> void:
    var scene := load("res://scenes/bootstrap.tscn") as PackedScene

    assert_that(scene).is_not_null()

    var bootstrap := scene.instantiate()
    assert_that(bootstrap is Node).is_true()
    assert_str(bootstrap.get_script().resource_path).is_equal(
        "res://scripts/bootstrap.gd"
    )
    bootstrap.free()
