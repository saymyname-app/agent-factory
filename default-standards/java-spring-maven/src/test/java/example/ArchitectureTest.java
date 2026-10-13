package __JAVA_PACKAGE__;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import com.tngtech.archunit.library.freeze.FreezingArchRule;
import org.junit.jupiter.api.Test;

class ArchitectureTest {
  @Test
  void persistenceDoesNotDependOnWeb() {
    JavaClasses classes = new ClassFileImporter().importPackages("__JAVA_PACKAGE__");
    FreezingArchRule.freeze(noClasses()
        .that()
        .resideInAPackage("..persistence..")
        .should()
        .dependOnClassesThat()
        .resideInAPackage("..web..")
        .allowEmptyShould(true))
        .check(classes);
  }
}
